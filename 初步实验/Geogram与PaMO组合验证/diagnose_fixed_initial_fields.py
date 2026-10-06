"""使用同一冻结初态顶点比较连续候选与累计参照的距离场差异。"""

import argparse
import json
from pathlib import Path

import numpy as np
import trimesh
import run_reference_cut_feedback
from audit_followup_candidate import sha256
from geometry_preservation_audit import MeshDistance
from audit_pamo_outputs import as_polydata
from geometry_error_distribution import distance_distribution
from run_geometry_study import now, save


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("batch", "prepared", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    path = args.batch / "01-统一配置完整父反馈记录.json"
    batch = json.loads(path.read_text("utf8"))
    manifest_path = args.prepared / "01-完整范围冻结清单.json"
    manifest = json.loads(manifest_path.read_text("utf8"))
    if batch["status"] == "running" or batch["manifest_sha256"] != sha256(manifest_path):
        raise ValueError("要求相同清单的路线终态")
    route = next(row for row in manifest["routes"] if row["id"] == batch["selected_route"])
    initial = args.prepared / "inputs" / route["initial_mesh"]
    if sha256(initial) != route["initial_mesh_sha256"]:
        raise ValueError("初态摘要不同")
    points = trimesh.load(initial, force="mesh", process=False).vertices
    args.output.mkdir(exist_ok=False)
    report = {"生成时间": now(), "修改时间及修改内容": "首次生成，固定初态探针比较连续距离场",
              "文档概述": "相同初态顶点到候选与累计参照的无符号距离之差，不使用变化的累计参照顶点集作为共同探针",
              "索引目录": ["rows"], "source_record_sha256": sha256(path), "initial_sha256": sha256(initial),
              "fixed_probe_count": len(points), "area_weighted": False, "new_GPU_calls": 0, "rows": []}
    for event in batch["rows"]:
        if event["status"] != "published_geometry_observation":
            continue
        stem = route["id"] + "_" + event["event"]
        candidate = args.batch / (stem + "_candidate_boolean") / "candidate.obj"
        reference = args.batch / (stem + "_reference") / "validated_reference.obj"
        if not reference.exists():
            reference = reference.with_name("reference.obj")
        if sha256(candidate) != event["output_sha256"] or sha256(reference) != event["reference_sha256"]:
            raise ValueError("实际候选或参照摘要不同")
        dc = MeshDistance(as_polydata(trimesh.load(candidate, force="mesh", process=False)))(points)
        dr = MeshDistance(as_polydata(trimesh.load(reference, force="mesh", process=True)))(points)
        delta = np.abs(dc - dr)
        worst = int(delta.argmax())
        # 距离场差异单独命名，不冒充面积比例、点到面距离或连续几何上界。
        row = {"event": event["event"], "candidate_sha256": sha256(candidate), "reference_sha256": sha256(reference),
               "distance_field_difference": distance_distribution(delta), "worst_initial_vertex_id": worst,
               "worst_position_mm": points[worst].tolist(), "candidate_distance_at_worst_mm": float(dc[worst]),
               "reference_distance_at_worst_mm": float(dr[worst]), "tail_initial_vertex_ids": np.flatnonzero(delta > .1).tolist()}
        report["rows"].append(row)
        print(event["event"], "maximum_field_difference", float(delta[worst]), flush=True)
    save(args.output / "01-固定初态顶点连续距离场差异诊断.json", report)


if __name__ == "__main__":
    main()
