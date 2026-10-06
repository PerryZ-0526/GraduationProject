"""复用已有父反馈控制器，对完整PaMO增加累计切削域排斥约束。"""

import argparse
import getpass
import json
from pathlib import Path
import re
import shutil
from time import perf_counter

import numpy as np
import trimesh

import run_constrained_feedback as controller
from run_constrained_batch import RemoteQuality, HERE
from run_geometry_study import now
from audit_followup_candidate import sha256, quality_distribution
from geometry_preservation_audit import mesh_valid
from positive_area_input import positive_area_input
from locality_masks import save_obj_fp64
from cut_exclusion import repair_cut_exclusion_many


class ExclusionEngine(RemoteQuality):
    prepared = None

    def __init__(self, output, port):
        # 沿用现有连接器，凭据只从忽略的本机环境读取，不进入日志或命令行。
        config_path = HERE.parents[1] / ".env"
        config = dict(line.split("=", 1) for line in config_path.read_text(encoding="utf-8").splitlines()
                      if line and not line.startswith("#"))
        original_prompt = getpass.getpass
        try:
            getpass.getpass = lambda _: config["CUDA_SSH_PASSWORD"]
            super().__init__(output, port)
        finally:
            getpass.getpass = original_prompt
            del config
        manifest = json.loads((self.prepared / "01-完整范围冻结清单.json").read_text(encoding="utf-8"))
        self.routes = {route["id"]: route for route in manifest["routes"]}

    def setup(self):
        info = super().setup()
        names = ("cut_exclusion.py", "run_cut_exclusion_feedback.py", "positive_area_input.py",
                 "run_constrained_feedback.py", "geometry_preservation_audit.py", "locality_cleanup.py")
        for name in names:
            shutil.copyfile(HERE / name, self.output / name)
        info.update(exclusion_code_sha256={name: sha256(HERE / name) for name in names},
                    input_policy="both_branches_positive_area_diagnostic_input_only",
                    output_policy="original_1e_12_area_topology_and_0_1_mm_geometry",
                    candidate_gpu_budget="one_original_full_PaMO_per_prefix_no_extra_candidate_attempts",
                    mechanism="full_PaMO_then_joint_cumulative_tool_face_support_QP_and_exact_face_anchor_check")
        return info

    def run(self, source, labels, tool, method, folder):
        match = re.fullmatch(r"(.+)_(e\d+)_(full|candidate)_(full|boolean|expanded)", Path(folder).name)
        if match is None:
            raise ValueError("无法识别已冻结路线与前缀")
        rid, event, branch, _ = match.groups()
        if branch == "candidate" and method != "boolean":
            # 控制器旧扩域/回退槽位保留为未运行状态，本机制只有一个冻结候选预算。
            return {"method": method, "execution": {"returncode": "not_registered_candidate_attempt"},
                    "status": "not_run_budget_excluded"}
        row = super().run(source, labels, tool, "full", folder)
        row.update(method=method, actual_gpu_method="original_full_PaMO")
        if row["execution"]["returncode"] or branch == "full":
            return row
        folder = Path(folder)
        raw = folder / "candidate.obj"
        shutil.copyfile(raw, folder / "raw_full_candidate.obj")
        route = self.routes[rid]
        current = route["cutting_prefix_ids"].index(event)
        retained = set(route["cutting_prefix_ids"][:current + 1])
        paths = [self.prepared / "inputs" / entry["mesh"] for entry in route["prefix_tools"]
                 if entry["event_id"] in retained]
        tools = [trimesh.load(path, force="mesh", process=False) for path in paths]
        mesh = trimesh.load(raw, force="mesh", process=False)
        start = perf_counter()
        candidate, details = repair_cut_exclusion_many(mesh, tools)
        details["correction_and_certificate_cpu_ms"] = (perf_counter() - start) * 1000
        details["cumulative_tool_sha256"] = [sha256(path) for path in paths]
        row.update(cut_exclusion=details, raw_full_output_sha256=sha256(raw))
        save_obj_fp64(candidate, raw)
        row["output_sha256"] = sha256(raw)
        (folder / "03-累计切削排斥记录.json").write_text(json.dumps(details, ensure_ascii=False, indent=2), encoding="utf-8")
        return row


def audit_exclusion(source_path, tool_path, labels_path, folder, row):
    """原版与候选共用输出门槛；候选还必须通过自身整面及锚点条件。"""
    if row["execution"]["returncode"]:
        return row
    start = perf_counter()
    source = trimesh.load(source_path, force="mesh", process=False)
    candidate = trimesh.load(Path(folder) / "candidate.obj", force="mesh", process=False)
    valid, metrics = mesh_valid(candidate)
    geometry = controller.global_geometry(candidate, source)
    log = (Path(folder) / "worker.log").read_text(encoding="utf-8")
    capacity = "exceeds max_blocks" in log or "Number of contacts" in log
    same_topology = (candidate.euler_number == source.euler_number
                     and len(candidate.split(only_watertight=False)) == len(source.split(only_watertight=False)))
    cut_passed = row.get("cut_exclusion", {}).get("accepted", True)
    passed = valid and same_topology and geometry["probe_max_mm"] <= .1 and not capacity and cut_passed
    row.update(output_metrics=metrics, geometry_to_maintenance_source=geometry,
               quality=quality_distribution(candidate), source_quality=quality_distribution(source),
               capacity_changed=capacity, continuous_geometry_certified=False,
               audited_source_sha256=sha256(source_path), independent_audit_ms=(perf_counter() - start) * 1000,
               status="accepted_sampled" if passed else "audit_rejected", audit_time_beijing=now())
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--split", required=True)
    args = parser.parse_args()
    ExclusionEngine.prepared = args.prepared
    # 同一控制器保证实际父哈希、累计独立参照及拒绝后保留版本的行为一致。
    controller.RemoteQuality = ExclusionEngine
    controller.mesh_valid = positive_area_input
    controller.audit_candidate = audit_exclusion
    controller.main()


if __name__ == "__main__":
    main()
