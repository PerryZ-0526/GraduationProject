"""重新加载完整验证的发布网格，复核拓扑及双向全顶点几何探针。"""

import argparse
import json
from pathlib import Path

import pyvista as pv
import trimesh

from audit_followup_candidate import sha256
from geometry_preservation_audit import mesh_valid
from run_constrained_feedback import global_geometry
from run_geometry_study import save, now


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = {"time_beijing": now(), "role": "保存网格重新加载重审，不改写原发布记录", "rows": []}
    for split in ("long", "application", "evaluation"):
        record_path = args.output / split / "01-反馈执行与独立审计.json"
        record = json.loads(record_path.read_text(encoding="utf-8"))
        if record["status"] != "completed_with_recorded_failures":
            raise ValueError("只重审已结束阶段")
        for row in record["rows"]:
            if row["status"] != "published_under_sampled_and_vertex_protocol":
                continue
            stem = row["route"] + "_" + row["event"]
            candidate_path = args.output / split / (stem + "_" + row["branch"] + "_" + row["selected_method"]) / "candidate.obj"
            candidate = trimesh.load(candidate_path, force="mesh", process=False)
            valid, metrics = mesh_valid(candidate)
            reference_folder = args.output / split / (stem + "_reference")
            analytic = reference_folder / "analytic_reference.vtp"
            reference_path = analytic if analytic.exists() else reference_folder / "reference.obj"
            reference = pv.read(reference_path) if analytic.exists() else trimesh.load(reference_path,
                force="mesh", process=True, validate=True)
            geometry = global_geometry(candidate, reference)
            source_path = args.output / split / (stem + "_" + row["branch"] + "_input") / "clean_source.obj"
            source = trimesh.load(source_path, force="mesh", process=False)
            _, source_metrics = mesh_valid(source)
            same_topology = (metrics["components"], metrics["euler_number"]) == (
                source_metrics["components"], source_metrics["euler_number"])
            passed = valid and same_topology and geometry["probe_max_mm"] <= .1 and sha256(candidate_path) == row["output_sha256"]
            report["rows"].append({"split": split, "route": row["route"], "event": row["event"],
                "branch": row["branch"], "candidate_sha256": sha256(candidate_path), "reference_sha256": sha256(reference_path),
                "valid": valid, "same_topology_as_csg": same_topology, "geometry": geometry, "passed": passed})
            save(args.output / "06-已发布保存网格独立重审.json", report)
        print(split, "重审累计", len(report["rows"]), flush=True)
    feature_record = json.loads((args.output / "features" / "02-浅磨特征保持审计.json").read_text(encoding="utf-8"))
    if feature_record["status"] != "completed_with_recorded_failures":
        raise ValueError("小特征阶段尚未结束")
    for row in feature_record["rows"]:
        if row["status"] != "accepted_sampled":
            continue
        candidate_path = args.output / "features" / (row["case"] + "_" + row["method"]) / "candidate.obj"
        source_path = args.output / "features" / (row["case"] + "_input") / "clean_source.obj"
        candidate = trimesh.load(candidate_path, force="mesh", process=False)
        source = trimesh.load(source_path, force="mesh", process=False)
        valid, metrics = mesh_valid(candidate)
        _, source_metrics = mesh_valid(source)
        topology = (metrics["components"], metrics["euler_number"]) == (source_metrics["components"], source_metrics["euler_number"])
        geometry = global_geometry(candidate, source)
        # 静态特征额外使用全部顶点探针；保留原面积采样结论，不静默改写。
        passed = valid and topology and geometry["probe_max_mm"] <= .1 and sha256(candidate_path) == row["output_sha256"]
        report["rows"].append({"split": "features", "case": row["case"], "method": row["method"],
            "candidate_sha256": sha256(candidate_path), "source_sha256": sha256(source_path),
            "valid": valid, "same_topology_as_csg": topology, "geometry": geometry, "passed": passed})
        save(args.output / "06-已发布保存网格独立重审.json", report)
    report.update(status="completed", rechecked_outputs=len(report["rows"]),
        passed=sum(r["passed"] for r in report["rows"]), continuous_geometry_certified=False)
    save(args.output / "06-已发布保存网格独立重审.json", report)
    print("重审", report["passed"], "/", report["rechecked_outputs"], flush=True)
    if report["passed"] != report["rechecked_outputs"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
