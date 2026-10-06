"""复用两个真实GPU几何负例，验证逆向覆盖补点，不改旧拒绝。"""

import argparse
import json
from pathlib import Path
from time import perf_counter

import trimesh

from run_reference_cut_feedback import ReferenceCutEngine
from cut_side_classifier import ExactCutSide
from coverage_adaptive_exclusion import coverage_adaptive_exclusion
from audit_followup_candidate import sha256, quality_distribution
from run_constrained_feedback import global_geometry
from locality_masks import save_obj_fp64
from run_geometry_study import execute, save, now


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--assets", type=Path, required=True)
    parser.add_argument("--side-validation", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    args.output.mkdir(exist_ok=False)
    assets = json.loads((args.assets / "01-排斥合法与覆盖失败真实负例清单.json").read_text("utf8"))
    ReferenceCutEngine.prepared = args.prepared
    engine = ReferenceCutEngine(args.output, args.port)
    report = {"生成时间": now(), "修改时间及修改内容": "首次生成，覆盖补点开发先冻结",
              "文档概述": "两已见失败首刀复用GPU，不是新独立或连续评价",
              "索引目录": ["protocol", "rows"], "status": "running", "rows": [],
              "asset_manifest_sha256": sha256(args.assets / "01-排斥合法与覆盖失败真实负例清单.json"),
              "protocol": {"new_GPU_calls": 0, "max_edge_refinement_levels": 4, "reverse_seed_passes": 5,
                           "reverse_trigger_mm": .025, "final_geometry_budget_mm": .1,
                           "per_face_seed_rule": "farthest_uncovered_reference_vertex_at_most_one"}}
    record = args.output / "01-双向覆盖补点首刀开发与审计.json"
    try:
        if execute(engine.client, ["mkdir", engine.remote])["returncode"]:
            raise ValueError("新开发远端目录已存在")
        validation = json.loads((args.side_validation / "01-精确侧分类器与骨面锚点验证.json").read_text("utf8"))
        if validation["status"] != "completed" or not all(t["passed"] for t in validation["tests"]):
            raise ValueError("精确分类器控制不通过")
        executable = validation["environment"]["executable"]
        if execute(engine.client, ["sha256sum", executable])["stdout"].split()[0] != validation["environment"]["executable_sha256"]:
            raise ValueError("精确分类器实际摘要不符")
        side = ExactCutSide(engine, executable)
        save(record, report)
        for case in assets["rows"]:
            folder = args.assets / case["case"]
            for name, digest in case["files"].items():
                if sha256(folder / name) != digest:
                    raise ValueError("真实负例资产摘要不符")
            raw = trimesh.load(folder / "实际GPU原对象.obj", force="mesh", process=False)
            reference = trimesh.load(folder / "独立累计参照.obj", force="mesh", process=True, validate=True)
            tool = trimesh.load(folder / "首刀工具.obj", force="mesh", process=False)
            source = trimesh.load(folder / "合法布尔源.obj", force="mesh", process=False)
            started = perf_counter()
            mesh, details = coverage_adaptive_exclusion(raw, [tool], reference, side.anchor)
            path = args.output / (case["case"] + "_candidate.obj")
            save_obj_fp64(mesh, path)
            geometry = global_geometry(mesh, source)
            row = {"case": case["case"], "details": details, "saved_sha256": sha256(path),
                   "source_geometry": geometry, "quality": quality_distribution(mesh),
                   "source_quality": quality_distribution(source),
                   "CPU_and_remote_audit_ms": (perf_counter() - started) * 1000,
                   "accepted": bool(details["accepted"] and geometry["probe_max_mm"] <= .1)}
            report["rows"].append(row)
            save(record, report)
            print(case["case"], "accepted", row["accepted"], "levels", len(details["attempts"]), flush=True)
        report.update(status="completed", finished_beijing=now())
        save(record, report)
    finally:
        engine.close()


if __name__ == "__main__":
    main()
