"""参照自适应排斥的开发父反馈入口；同输入共享GPU，精确实体锚点发布门控。"""

import argparse
import json
from pathlib import Path
import re
import shutil
import sys
from time import perf_counter

import trimesh

import run_constrained_feedback as controller
import run_cut_exclusion_feedback as first
from run_constrained_batch import RemoteQuality
from run_cut_exclusion_continuation import CertifiedCutEngine, audit
from run_cut_exclusion_paired import shared_gpu, shared_csg
from run_cut_exclusion_recovery import exact_recovery
from cut_side_classifier import ExactCutSide
from reference_adaptive_exclusion import reference_adaptive_exclusion
from audit_followup_candidate import sha256
from audit_cut_embedding import CHECKER
from locality_masks import save_obj_fp64
from run_geometry_study import execute, save, now
from study_cut_exclusion import input_valid
from exact_alarm_contact import mesh_valid_exact_contacts
from locality_cleanup import clean_provenance
from locality_diagnostic import source_region, verify_labels


class ReferenceCutEngine(CertifiedCutEngine):
    side_validation = None

    def setup(self):
        info = super().setup()
        validation = json.loads((self.side_validation / "01-精确侧分类器与骨面锚点验证.json").read_text("utf8"))
        if validation["status"] != "completed" or not all(x["passed"] for x in validation["tests"]):
            raise ValueError("精确分类器控制未通过")
        executable = validation["environment"]["executable"]
        if execute(self.client, ["sha256sum", executable])["stdout"].split()[0] != validation["environment"]["executable_sha256"]:
            raise ValueError("已验证精确分类器已改变")
        self.side = ExactCutSide(self, executable)
        info["actual_parameters"].update(max_refinement_levels=4, geometry_trigger_mm=.025,
            restoration_raw_displacement_budget_enforced=False, correction_budget_origin="each_reference_seed",
            anchor="exact_material_side_after_full_EPECK_embedding", role="seen_public_bone_development_feedback")
        info["reference_adaptive_sha256"] = sha256(Path(__file__).with_name("reference_adaptive_exclusion.py"))
        save(self.output / "03-实际分支协议冻结.json", {"生成时间": now(),
            "修改时间及修改内容": "首次候选执行前替换继承模板为新实际协议", "文档概述": "参照自适应开发父反馈",
            "索引目录": ["environment"], "environment": info})
        return info

    def run(self, source, labels, tool, method, folder):
        rid, event, branch, _ = re.fullmatch(r"(.+)_(e\d+)_(full|candidate)_(full|boolean|expanded)", Path(folder).name).groups()
        if branch == "candidate" and method != "boolean":
            return {"method": method, "execution": {"returncode": "not_registered_candidate_attempt"}, "status": "not_run_budget_excluded"}
        row = RemoteQuality.run(self, source, labels, tool, "full", folder)
        row.update(method=method, actual_gpu_method="original_full_PaMO")
        if row["execution"]["returncode"]:
            return row
        path = Path(folder) / "candidate.obj"
        if branch == "candidate":
            shutil.copyfile(path, Path(folder) / "raw_full_candidate.obj")
            route = self.routes[rid]
            prefix = set(route["cutting_prefix_ids"][:route["cutting_prefix_ids"].index(event) + 1])
            tools_paths = [self.prepared / "inputs" / t["mesh"] for t in route["prefix_tools"] if t["event_id"] in prefix]
            reference_folder = self.output / f"{rid}_{event}_reference"
            reference_path = reference_folder / "validated_reference.obj"
            if not reference_path.exists():
                reference_path = reference_folder / "reference.obj"
            reference = trimesh.load(reference_path, force="mesh", process=True, validate=True)
            tools = [trimesh.load(p, force="mesh", process=False) for p in tools_paths]
            started = perf_counter()
            mesh, details = reference_adaptive_exclusion(trimesh.load(path, force="mesh", process=False), tools, reference, self.side.anchor)
            details.update(correction_cpu_and_remote_audit_ms=(perf_counter() - started) * 1000,
                           cumulative_tool_sha256=[sha256(p) for p in tools_paths], cumulative_reference_sha256=sha256(reference_path))
            row.update(cut_exclusion=details, raw_full_output_sha256=sha256(path))
            save_obj_fp64(mesh, path)
            save(Path(folder) / "03-参照自适应排斥记录.json", details)
        row["output_sha256"] = sha256(path)
        # 发布前独立核对实际保存对象，不能把内存候选的嵌入证据绑定到另一个文件。
        remote = self.remote + "/" + Path(folder).name + "/saved_for_embedding_audit.obj"
        self.sftp.put(str(path), remote)
        if execute(self.client, ["sha256sum", remote])["stdout"].split()[0] != sha256(path):
            raise ValueError("保存嵌入审计摘要不匹配")
        run = execute(self.client, [CHECKER, remote], timeout=120)
        row["exact_embedding"] = {"execution": run, "saved_sha256": sha256(path)}
        if not run["returncode"]:
            row["exact_embedding"].update(json.loads(run["stdout"]))
        return row


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--split", required=True)
    parser.add_argument("--side-validation", type=Path, required=True)
    args = parser.parse_args()
    ReferenceCutEngine.prepared = args.prepared
    ReferenceCutEngine.side_validation = args.side_validation
    RemoteQuality.run = shared_gpu
    controller.execute = shared_csg
    controller.RemoteQuality = ReferenceCutEngine
    controller.REFERENCE_RECOVERY = exact_recovery
    controller.mesh_valid = input_valid
    controller.VALID_SOURCE_BITS = (1, 2, 3)
    controller.clean_provenance = lambda mesh, bits: clean_provenance(mesh, bits, allow_shared=True)
    controller.source_region = lambda mesh, bits: source_region(mesh, bits, allow_shared=True)
    controller.verify_labels = lambda *values: verify_labels(*values, allow_shared=True)
    first.mesh_valid = mesh_valid_exact_contacts
    controller.audit_candidate = audit
    # 共享控制器只解析其原有参数，分类器路径已由新入口保存到引擎类。
    option = sys.argv.index("--side-validation")
    del sys.argv[option:option + 2]
    controller.main()
