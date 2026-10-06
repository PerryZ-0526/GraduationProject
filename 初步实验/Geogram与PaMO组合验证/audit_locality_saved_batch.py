"""审计保存帧开发批次，并将上游拒绝纳入完整八帧分母。"""

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
from locality_diagnostic import conservative_far_faces, digest, far_drift
from locality_masks import external_contract, make_masks
from motion_record import replay_case


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    manifest_path = args.prepared / "01-保存帧开发批次.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    remote = json.loads((args.candidates / "01-开发执行汇总.json").read_text(encoding="utf-8"))
    if remote["manifest_sha256"] != digest(manifest_path):
        raise ValueError("实际批次清单摘要不符")
    c1 = json.loads((HERE / "实验结果/20260929_C1试运行准备/01-C1试运行清单.json").read_text(encoding="utf-8"))
    policy = json.loads((HERE / "实验结果/20260928_后续输入冻结_v3/02-评价协议.json").read_text(encoding="utf-8"))["replay_policy"]
    report = {"time_beijing": datetime.now(timezone(timedelta(hours=8))).isoformat(),
              "role": manifest["role"], "manifest_sha256": digest(manifest_path), "cases": [], "rows": []}
    for case in manifest["cases"]:
        report["cases"].append({"case": case["case"], "input_valid": case["input_valid"],
                                "status": "audit_pending" if case["input_valid"] else "input_rejected"})
        if not case["input_valid"]:
            continue
        inputs = args.prepared / case["case"]
        outputs = args.candidates / case["case"]
        execution = json.loads((outputs / "01-GPU执行记录.json").read_text(encoding="utf-8"))
        for name, sha in case["files_sha256"].items():
            if digest(inputs / name) != sha:
                raise ValueError("本地输入变化: " + case["case"])
        for name, filename in (("source", "source.obj"), ("labels", "labels.json"), ("tool", "tool.obj")):
            if execution[name + "_sha256"] != case["files_sha256"][filename]:
                raise ValueError("远端实际输入变化: " + case["case"])
        source = trimesh.load(inputs / "source.obj", force="mesh", process=False)
        tool = trimesh.load(inputs / "tool.obj", force="mesh", process=False)
        bits = json.loads((inputs / "labels.json").read_text())["operand_bits"]
        route = next(r for r in c1["routes"] if r["id"] == case["route"])
        primitives = replay_case(route, policy, case["event"])["primitives"]
        reference = HERE / "实验结果/20260928_开发解析参照" / case["reference"]["mesh"]
        if digest(reference) != case["reference"]["sha256"]:
            raise ValueError("独立参照变化")
        for row in execution["rows"]:
            start = perf_counter()
            stem = f"r{row['round']}_{row['method']}"
            target = outputs / (stem + ".obj")
            result = {"case": case["case"], "route": case["route"], "event": case["event"],
                      "method": row["method"], "round": row["round"], "maintenance_wall_ms": row["wall_ms"],
                      "active_fraction": row.get("active_fraction"), "accepted_sampled": False}
            if row["child_status"] == 0 and target.is_file():
                if digest(target) != row["output_sha256"]:
                    raise ValueError("候选变化: " + stem)
                mesh = trimesh.load(target, force="mesh", process=False)
                metrics = audit_one(inputs / "source.obj", target, reference)
                quality = quality_distribution(mesh)
                # 变化区由独立物理扫掠定义，不能各方法自行选择好看的评价区域。
                roi = trimesh.Trimesh(mesh.vertices, mesh.faces[~conservative_far_faces(mesh, primitives)], process=False)
                manifold = vertex_manifold_closed(mesh.faces)
                contract = None
                if row["method"] != "full":
                    ids = np.load(outputs / (stem + "_original_ids.npy"))
                    mode = "boolean" if row["method"] in ("boolean_no_transition", "boolean_no_boundary") else row["method"]
                    active, fixed = make_masks(source, bits, tool, mode,
                                               rings=0 if row["method"] == "boolean_no_transition" else 2)
                    contract = external_contract(source, mesh, ids, active, fixed)
                log = (outputs / (stem + ".log")).read_text(encoding="utf-8")
                capacity_change = "exceeds max_blocks" in log or "Number of contacts" in log
                passed = bool(metrics["topology_passed"] and metrics["sampled_geometry_passed"] and
                              manifold and quality["invalid_faces"] == 0 and
                              (contract is None or contract["passed"]) and not capacity_change)
                result.update(accepted_sampled=passed, quality=quality, metrics=metrics,
                              quality_sweep_affected=quality_distribution(roi),
                              source_quality=quality_distribution(source), fixed_contract=contract,
                              capacity_changed=capacity_change, far_drift=far_drift(source, mesh, primitives),
                              continuous_geometry_certified=False)
            else:
                result["error"] = row.get("error")
            result["independent_audit_ms"] = (perf_counter() - start) * 1000
            result["maintenance_plus_audit_ms"] = row["wall_ms"] + result["independent_audit_ms"]
            report["rows"].append(result)
            args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(case["case"], row["method"], result["accepted_sampled"], flush=True)
        report["cases"][-1]["status"] = "audited"
    report["status"] = "completed"
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
