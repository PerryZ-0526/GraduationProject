"""定位观察路线的超差顶点，来源最近面和工具距离仅作空间诊断。"""

import argparse
import json
from pathlib import Path

import numpy as np
import trimesh
from vtkmodules.vtkCommonCore import reference as vtk_reference
import run_reference_cut_feedback
from audit_pamo_outputs import as_polydata
from geometry_preservation_audit import MeshDistance
from audit_followup_candidate import sha256
from run_geometry_study import now, save


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    record_path = args.batch / "01-统一配置完整父反馈记录.json"
    batch = json.loads(record_path.read_text("utf8"))
    manifest_path = args.prepared / "01-完整范围冻结清单.json"
    if batch["manifest_sha256"] != sha256(manifest_path) or batch["status"] == "running":
        raise ValueError("要求相同输入清单的路线终态")
    manifest = json.loads(manifest_path.read_text("utf8"))
    route = next(row for row in manifest["routes"] if row["id"] == batch["selected_route"])
    args.output.mkdir(exist_ok=False)
    report = {"生成时间": now(), "修改时间及修改内容": "首次生成，超0.1毫米顶点位置只读定位",
              "文档概述": "定位真实误差尾部，不修改网格或固定几何评价门槛；最近来源面不是严格对应证书",
              "索引目录": ["rows"], "source_record_sha256": sha256(record_path), "new_GPU_calls": 0, "rows": []}
    for event in batch["rows"]:
        if event["status"] != "published_geometry_observation":
            continue
        stem = route["id"] + "_" + event["event"]
        candidate_path = args.batch / (stem + "_candidate_boolean") / "candidate.obj"
        source_path = args.batch / (stem + "_candidate_input") / "clean_source.obj"
        reference_path = args.batch / (stem + "_reference") / "validated_reference.obj"
        if not reference_path.exists():
            reference_path = reference_path.with_name("reference.obj")
        if sha256(candidate_path) != event["output_sha256"] or sha256(source_path) != event["attempt"]["inputs_sha256"]["source.obj"] or sha256(reference_path) != event["reference_sha256"]:
            raise ValueError("实际候选、源或累计参照变化")
        candidate = trimesh.load(candidate_path, force="mesh", process=False)
        source = trimesh.load(source_path, force="mesh", process=False)
        cumulative = trimesh.load(reference_path, force="mesh", process=True)
        labels = source_path.with_name("clean_labels.json")
        if sha256(labels) != event["attempt"]["inputs_sha256"]["labels.json"]:
            raise ValueError("实际来源标签变化")
        bits = json.loads(labels.read_text("utf8"))["operand_bits"]
        source_locator = MeshDistance(as_polydata(source))
        tool_queries = []
        prefix = route["cutting_prefix_ids"][:route["cutting_prefix_ids"].index(event["event"]) + 1]
        for tool in route["prefix_tools"]:
            if tool["event_id"] in prefix:
                path = args.prepared / "inputs" / tool["mesh"]
                if sha256(path) != tool["sha256"]:
                    raise ValueError("累计工具变化")
                tool_queries.append(MeshDistance(as_polydata(trimesh.load(path, force="mesh", process=False))))
        rows = []
        for direction, mesh, target in (("candidate_to_cumulative", candidate, cumulative), ("cumulative_to_candidate", cumulative, candidate)):
            distances = MeshDistance(as_polydata(target))(mesh.vertices)
            ids = np.flatnonzero(distances > .1)
            points = mesh.vertices[ids]
            tool_distances = np.min(np.stack([query(points) for query in tool_queries]), axis=0) if len(ids) else np.empty(0)
            vertices = []
            for index, point, tool_distance in zip(ids, points, tool_distances):
                nearest, cid, sid, square = [0.] * 3, vtk_reference(0), vtk_reference(0), vtk_reference(0.)
                source_locator.locator.FindClosestPoint(point, nearest, cid, sid, square)
                vertices.append({"vertex_id": int(index), "position_mm": point.tolist(), "error_mm": float(distances[index]),
                                 "nearest_source_face_id": int(cid), "nearest_source_operand_bits": int(bits[int(cid)]),
                                 "distance_to_source_mm": float(np.sqrt(float(square))), "distance_to_prefix_tool_surface_mm": float(tool_distance)})
            rows.append({"direction": direction, "vertex_denominator": len(distances), "tail_vertices": len(ids),
                         "tail_vertex_fraction": float(len(ids) / len(distances)), "vertices": vertices})
        report["rows"].append({"event": event["event"], "candidate_sha256": sha256(candidate_path), "directions": rows})
        print(event["event"], [(row["direction"], row["tail_vertices"]) for row in rows], flush=True)
    save(args.output / "01-超差顶点与最近来源工具空间定位.json", report)


if __name__ == "__main__":
    main()
