"""在已嵌入且排斥合法的细化负例上，只恢复超过最终门槛的漏覆盖区域。"""

import argparse
import json
from pathlib import Path

import trimesh

from run_reference_cut_feedback import ReferenceCutEngine
from cut_side_classifier import ExactCutSide
from reverse_coverage_targets import restore_reverse_coverage_targets
from cut_exclusion import repair_cut_exclusion_many
from exact_embedding_gate import mesh_valid_full_embedding
from run_constrained_feedback import global_geometry
from audit_followup_candidate import sha256, quality_distribution
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
    data = json.loads((args.assets / "01-排斥合法与覆盖失败真实负例清单.json").read_text("utf8"))
    ReferenceCutEngine.prepared = args.prepared
    engine = ReferenceCutEngine(args.output, args.port)
    report = {"生成时间": now(), "修改时间及修改内容": "首次生成，一次局部逆向恢复提案先冻结",
              "文档概述": "仅两个已见细化负例，不改已失败早期恢复版本",
              "索引目录": ["protocol", "rows"], "status": "running", "rows": [],
              "protocol": {"new_GPU_calls": 0, "reverse_trigger_mm": .1, "extra_reverse_passes": 1,
                           "final_geometry_budget_mm": .1, "additional_edge_refinement": 0}}
    record = args.output / "01-合法细化网格局部覆盖恢复开发.json"
    try:
        if execute(engine.client, ["mkdir", engine.remote])["returncode"]:
            raise ValueError("局部恢复审计目录已存在")
        validation = json.loads((args.side_validation / "01-精确侧分类器与骨面锚点验证.json").read_text("utf8"))
        executable = validation["environment"]["executable"]
        if execute(engine.client, ["sha256sum", executable])["stdout"].split()[0] != validation["environment"]["executable_sha256"]:
            raise ValueError("实际精确分类器摘要不符")
        side = ExactCutSide(engine, executable)
        save(record, report)
        for case in data["rows"]:
            folder = args.assets / case["case"]
            for name, digest in case["files"].items():
                if sha256(folder / name) != digest:
                    raise ValueError("冻结负例输入已改变")
            original = trimesh.load(folder / "排斥合法但几何失败候选.obj", force="mesh", process=False)
            reference = trimesh.load(folder / "独立累计参照.obj", force="mesh", process=True, validate=True)
            tool = trimesh.load(folder / "首刀工具.obj", force="mesh", process=False)
            source = trimesh.load(folder / "合法布尔源.obj", force="mesh", process=False)
            seed, restoration = restore_reverse_coverage_targets(original, reference, tolerance=.1)
            candidate, details = repair_cut_exclusion_many(seed, [tool], target_vertices=seed.vertices, anchor_classifier=side.anchor)
            path = args.output / (case["case"] + "_candidate.obj")
            save_obj_fp64(candidate, path)
            geometry, source_geometry = global_geometry(candidate, reference), global_geometry(candidate, source)
            valid = False
            checks = {}
            if details["accepted"]:
                anchors = details["outside_anchor_certificate"]
                anchor = anchors if isinstance(anchors, dict) else anchors[0]
                valid, checks = mesh_valid_full_embedding(candidate, anchor["classification"])
            row = {"case": case["case"], "restoration": restoration, "cut_exclusion": details,
                   "saved_sha256": sha256(path), "geometry": geometry, "source_geometry": source_geometry,
                   "checks": checks, "quality": quality_distribution(candidate),
                   "accepted": bool(details["accepted"] and valid and geometry["probe_max_mm"] <= .1
                                    and source_geometry["probe_max_mm"] <= .1)}
            report["rows"].append(row)
            save(record, report)
            print(case["case"], "local_reverse_accepted", row["accepted"], "C0", geometry["probe_max_mm"], flush=True)
        report.update(status="completed", finished_beijing=now())
        save(record, report)
    finally:
        engine.close()


if __name__ == "__main__":
    main()
