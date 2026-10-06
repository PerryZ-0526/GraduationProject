"""冻结静态切削排斥机制，在每个保留几何体的首刀共享原版PaMO输出作独立对照。"""

import getpass
import json
from pathlib import Path
import shutil
from time import perf_counter

import numpy as np
import trimesh

from audit_followup_candidate import sha256, quality_distribution
from geometry_preservation_audit import mesh_valid
from exact_alarm_contact import mesh_valid_exact_contacts
from positive_area_input import positive_area_input
from locality_cleanup import clean_provenance
from locality_masks import save_obj_fp64
from run_constrained_feedback import global_geometry, PROVENANCE
from run_constrained_batch import RemoteQuality, HERE
from run_geometry_study import execute, retrieve, save, now
from cut_exclusion import repair_cut_exclusion
from probe_removed_material import tool_clearance
from pilot_cut_exclusion import nearest_projection, vertex_only_projection


def input_valid(mesh):
    """两组统一采用正面积输入诊断和报警集合精确复核，不放宽输出面积门槛。"""
    valid, metrics = positive_area_input(mesh)
    if metrics.get("self_intersection_faces", 0):
        _, extra = mesh_valid_exact_contacts(mesh)
        metrics["exact_alarm_pair_proofs"] = extra.get("exact_alarm_pair_proofs", [])
        metrics["self_intersection_faces"] = extra["self_intersection_faces"]
        valid = all((metrics["finite"], metrics["watertight"], metrics["winding_consistent"],
                     metrics["vertex_manifold_closed"], metrics["zero_area_faces"] == 0,
                     metrics["fp32_zero_area_faces"] == 0, metrics["self_intersection_faces"] == 0))
    return valid, metrics


def main():
    prepared = HERE.parent / "可复用磨削测试集/连续输入_v1"
    manifest_path = prepared / "01-完整范围冻结清单.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    routes = [r for r in manifest["routes"] if r["split"] == "evaluation" and r["id"].endswith("_交叉")]
    if len(routes) != 21:
        raise ValueError("独立几何体数量不是冻结的21")
    output = HERE / "实验结果/20261004_切削排斥21几何体独立静态验证"
    output.mkdir(exist_ok=False)
    for name in ("cut_exclusion.py", "study_cut_exclusion.py", "pilot_cut_exclusion.py", "positive_area_input.py",
                 "exact_alarm_contact.py", "geometry_preservation_audit.py", "locality_cleanup.py"):
        shutil.copyfile(HERE / name, output / name)
    frozen = {"生成时间": now(), "修改时间及修改内容": "首次冻结，先于独立候选输出",
              "文档概述": "21保留几何体的交叉首刀；同一次PaMO输出用于全部修正对照，不是连续验证",
              "索引目录": ["parameters", "routes", "source_hashes"],
              "parameters": {"correction_budget_mm": .1, "clearance_mm": 1e-8, "objective_target": "raw_maintained_vertices",
                             "target_vertices": None, "input_policy": "positive_area_plus_exact_alarm_contacts",
                             "output_policy": "unchanged_1e_12_area_with_same_exact_alarm_contacts", "pamo_calls_budget": 21},
              "routes": [r["id"] for r in routes], "manifest_sha256": sha256(manifest_path),
              "source_hashes": {p.name: sha256(p) for p in output.glob("*.py")}}
    save(output / "01-独立静态方法冻结.json", frozen)
    config = dict(line.split("=", 1) for line in (HERE.parents[1] / ".env").read_text(encoding="utf-8").splitlines()
                  if line and not line.startswith("#"))
    original_prompt = getpass.getpass
    try:
        getpass.getpass = lambda _: config["CUDA_SSH_PASSWORD"]
        engine = RemoteQuality(output, int(config["CUDA_SSH_PORT"]))
    finally:
        getpass.getpass = original_prompt
        del config
    report = {"生成时间": now(), "修改时间及修改内容": "首次执行，全部失败保留",
              "文档概述": frozen["文档概述"], "索引目录": ["environment", "rows"], "rows": [], "status": "running"}
    record = output / "02-独立静态执行与审计.json"
    try:
        report["environment"] = engine.setup()
        report["environment"]["provenance_sha256"] = execute(engine.client, ["sha256sum", PROVENANCE])["stdout"].split()[0]
        save(record, report)
        for route in routes:
            rid = route["id"]
            item = {"route": rid, "source_kind": route["source_kind"], "status": "input_preflight"}
            report["rows"].append(item)
            folder = output / rid
            folder.mkdir()
            initial = prepared / "inputs" / route["initial_mesh"]
            first = next(t for t in route["prefix_tools"] if t["event_id"] == route["cutting_prefix_ids"][0])
            tool_path = prepared / "inputs" / first["mesh"]
            for path, expected in ((initial, route["initial_mesh_sha256"]), (tool_path, first["sha256"])):
                if sha256(path) != expected:
                    raise ValueError("冻结输入摘要改变")
            item["input_hashes"] = {str(p): sha256(p) for p in (initial, tool_path)}
            remote_initial, remote_tool, remote_source, remote_labels = [engine.remote + f"/{rid}_{name}" for name in
                                                                       ("initial.obj", "tool.obj", "source.obj", "labels.json")]
            for path, remote in ((initial, remote_initial), (tool_path, remote_tool)):
                engine.sftp.put(str(path), remote)
            item["csg"] = execute(engine.client, [PROVENANCE, remote_initial, remote_tool, remote_source, remote_labels, "--no-simplify"],
                                  engine.remote + f"/{rid}_csg.log", timeout=120)
            retrieve(engine.client, engine.sftp, engine.remote + f"/{rid}_csg.log", folder / "csg.log")
            if item["csg"]["returncode"]:
                item["status"] = "csg_execution_failed"
                save(record, report)
                continue
            for name, remote in (("raw_source.obj", remote_source), ("raw_labels.json", remote_labels)):
                retrieve(engine.client, engine.sftp, remote, folder / name)
            raw = trimesh.load(folder / "raw_source.obj", force="mesh", process=False)
            bits = json.loads((folder / "raw_labels.json").read_text())["operand_bits"]
            try:
                source, labels, cleanup = clean_provenance(raw, bits)
            except ValueError as error:
                item.update(status="source_cleanup_rejected", reason=str(error))
                save(record, report)
                continue
            valid, checks = input_valid(source)
            item.update(input_checks=checks, cleanup=cleanup)
            if not valid:
                item["status"] = "source_preflight_rejected"
                save(record, report)
                continue
            source_path, labels_path = folder / "source.obj", folder / "labels.json"
            save_obj_fp64(source, source_path)
            save(labels_path, {"operand_bits": labels.tolist()})
            run = engine.run(source_path, labels_path, tool_path, "full", output / f"{rid}_shared_full")
            item["shared_full_execution"] = run
            if run["execution"]["returncode"]:
                item["status"] = "shared_gpu_execution_failed"
                save(record, report)
                continue
            shared = trimesh.load(output / f"{rid}_shared_full/candidate.obj", force="mesh", process=False)
            tool = trimesh.load(tool_path, force="mesh", process=False)
            capacity = any(s in (output / f"{rid}_shared_full/worker.log").read_text(encoding="utf-8")
                           for s in ("exceeds max_blocks", "Number of contacts"))
            item["methods"] = {}
            for method in ("full", "nearest", "vertex_only", "exclusion"):
                start = perf_counter()
                if method == "full":
                    candidate, details = shared.copy(), {}
                elif method == "nearest":
                    candidate, details = nearest_projection(shared, source), {}
                elif method == "vertex_only":
                    candidate, details = vertex_only_projection(shared, tool), {}
                else:
                    candidate, details = repair_cut_exclusion(shared, tool)
                details["correction_cpu_ms"] = (perf_counter() - start) * 1000
                save_obj_fp64(candidate, folder / f"{method}.obj")
                valid, metrics = mesh_valid_exact_contacts(candidate)
                geometry = global_geometry(candidate, source)
                topology = candidate.euler_number == source.euler_number and metrics["components"] == checks["components"]
                movement = float(np.linalg.norm(candidate.vertices - shared.vertices, axis=1).max(initial=0))
                accepted = valid and topology and geometry["probe_max_mm"] <= .1 and movement <= .1 and not capacity
                if method == "exclusion":
                    accepted = accepted and details["accepted"]
                probes = tool_clearance(np.concatenate((candidate.vertices, candidate.triangles_center)), tool)
                item["methods"][method] = {"accepted": bool(accepted), "details": details, "mesh_valid": valid,
                    "checks": metrics, "geometry": geometry, "quality": quality_distribution(candidate),
                    "inside_probe_count": int(np.sum(probes < -1e-7)), "max_inward_plane_depth_mm": max(0., -float(probes.min())),
                    "max_correction_mm": movement, "capacity_changed": capacity}
            item["status"] = "completed_with_recorded_method_outcomes"
            save(record, report)
            print(rid, [(name, value["accepted"], value["inside_probe_count"], value["geometry"]["probe_max_mm"])
                        for name, value in item["methods"].items()], flush=True)
        report.update(status="completed_with_recorded_failures", finished_beijing=now())
        save(record, report)
    finally:
        engine.close()


if __name__ == "__main__":
    main()
