"""独立审计局部GPU输出，核对几何、拓扑、质量与外部固定契约。"""

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
from time import perf_counter

import numpy as np
import trimesh

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "共同运动记录与方法对照"))
from audit_pamo_outputs import audit_one
from audit_followup_candidate import quality_distribution, vertex_manifold_closed
from locality_diagnostic import digest, far_drift, mesh_pair_drift
from locality_masks import external_contract, make_masks
from motion_record import replay_case


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    out = args.prepared / "取回输出/pilot_v2"
    execution = json.loads((out / "01-GPU执行记录.json").read_text(encoding="utf-8"))
    frozen = json.loads((args.prepared / "01-首帧试跑冻结.json").read_text(encoding="utf-8"))
    for name, sha in frozen["files_sha256"].items():
        if digest(args.prepared / name) != sha:
            raise ValueError("试跑代码或输入摘要改变: " + name)
    for name in ("source", "tool", "labels"):
        path = args.prepared / (name + (".json" if name == "labels" else ".obj"))
        if digest(path) != execution[name + "_sha256"]:
            raise ValueError("远端实际输入摘要不符: " + name)
    if digest(args.prepared / "取回输出/build/pamo_locality_cuda.so") != execution["extension_sha256"]:
        raise ValueError("实际CUDA扩展摘要不匹配")
    c1 = json.loads((HERE / "实验结果/20260929_C1试运行准备/01-C1试运行清单.json").read_text(encoding="utf-8"))
    route = next(r for r in c1["routes"] if r["category"] == "crossing")
    ref = next(r for r in c1["references"] if r["event"] == "e0" and r["route"] == route["id"])
    reference_path = HERE / "实验结果/20260928_开发解析参照" / ref["mesh"]
    if digest(reference_path) != ref["sha256"]:
        raise ValueError("独立离散参照摘要不匹配")
    protocol = json.loads((HERE / "实验结果/20260928_后续输入冻结_v3/02-评价协议.json").read_text(encoding="utf-8"))
    primitives = replay_case(route, protocol["replay_policy"], "e0")["primitives"]
    source = trimesh.load(args.prepared / "source.obj", force="mesh", process=False)
    tool = trimesh.load(args.prepared / "tool.obj", force="mesh", process=False)
    bits = json.loads((args.prepared / "labels.json").read_text())["operand_bits"]
    report = {"time_beijing": datetime.now(timezone(timedelta(hours=8))).isoformat(),
              "pilot_only": True, "execution_sha256": digest(out / "01-GPU执行记录.json"),
              "source_quality": quality_distribution(source), "rows": []}
    for row in execution["rows"]:
        start = perf_counter()
        stem = f"r{row['round']}_{row['method']}"
        target = out / (stem + ".obj")
        result = {"method": row["method"], "round": row["round"], "execution_status": row["status"],
                  "maintenance_wall_ms": row["wall_ms"]}
        if row["child_status"] == 0 and target.is_file():
            if digest(target) != row["output_sha256"]:
                raise ValueError("候选摘要改变: " + stem)
            mesh = trimesh.load(target, force="mesh", process=False)
            metrics = audit_one(args.prepared / "source.obj", target, reference_path)
            quality = quality_distribution(mesh)
            manifold = vertex_manifold_closed(mesh.faces)
            contract = None
            if row["method"] != "full":
                ids = np.load(out / (stem + "_original_ids.npy"))
                active, fixed = make_masks(source, bits, tool, row["method"])
                contract = external_contract(source, mesh, ids, active, fixed)
            log = (out / (stem + ".log")).read_text(encoding="utf-8")
            capacity_changed = "exceeds max_blocks" in log or "Number of contacts" in log
            passed = bool(metrics["topology_passed"] and metrics["sampled_geometry_passed"] and
                          manifold and quality["invalid_faces"] == 0 and
                          (contract is None or contract["passed"]) and not capacity_changed)
            result.update({"candidate_sha256": digest(target), "accepted_sampled": passed,
                           "quality": quality, "metrics": metrics, "vertex_manifold": manifold,
                           "fixed_contract_after_reload": contract, "capacity_change_detected": capacity_changed,
                           "far_drift": far_drift(source, mesh, primitives),
                           "source_pair_drift": mesh_pair_drift(source, mesh),
                           "continuous_geometry_certified": False})
        else:
            result.update(accepted_sampled=False, error=row.get("error"))
        result["independent_audit_ms"] = (perf_counter() - start) * 1000
        result["maintenance_plus_audit_ms"] = row["wall_ms"] + result["independent_audit_ms"]
        report["rows"].append(result)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(result["method"], result["accepted_sampled"], result.get("quality", {}).get("angle_below_10_deg"), flush=True)
    report["status"] = "completed"
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
