"""先冻结扫描探针，再比较实际发布实体与同事件独立累计参照。"""
import argparse
import json
from pathlib import Path
import numpy as np
import trimesh
from feature_line_audit import material_intervals, compare_intervals
from verify_precision_resume import digest, read
from run_geometry_study import now


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--record", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    record = read(args.record)
    if record["status"] != "completed_with_recorded_failures":
        raise ValueError("只审查完整终态")
    manifest_path = args.prepared / "01-完整范围冻结清单.json"
    routes = read(manifest_path)["routes"]
    probes = {}
    for route in routes:
        family = route["id"].split("_")[0]
        if family not in ("薄壁", "窄缝", "贯通孔"):
            continue
        path = args.prepared / "inputs" / route["initial_mesh"]
        if digest(path) != route["initial_mesh_sha256"]:
            raise ValueError("探针初态摘要不一致")
        initial = trimesh.load(path, process=False)
        axis = 2 if family == "薄壁" else 0
        indices = [index for index in range(3) if index != axis]
        scales = initial.extents.copy()
        if family == "贯通孔":
            scales[1] = np.linalg.norm(initial.vertices[:, :2], axis=1).min()
        entries = []
        for first in (-.317, .137, .293):
            for second in (-.317, .137, .293):
                position = np.zeros(3)
                position[indices[0]] = first*scales[indices[0]]
                position[indices[1]] = second*scales[indices[1]]
                entries.append({"axis": axis, "position_mm": position.tolist()})
        probes[route["id"]] = entries
    args.output.mkdir(parents=True, exist_ok=False)
    frozen = {"time_beijing": now(), "probes": probes, "record_sha256": digest(args.record),
              "manifest_sha256": digest(manifest_path),
              "code_sha256": digest(Path(__file__).with_name("feature_line_audit.py")),
              "scope": "仅由冻结初态决定的九条扫描线；不是整特征最小厚度或开口保证"}
    (args.output / "01-固定扫描探针.json").write_text(json.dumps(frozen, ensure_ascii=False, indent=2), encoding="utf-8")
    rows = []
    for row in record["rows"]:
        if row["route"] not in probes or row["branch"] == "R" or row["status"] != "published_under_sampled_and_vertex_protocol":
            continue
        root = Path(row.get("source_output_directory", args.record.parent))
        stem = row["route"] + "_" + row["event"]
        candidate_path = root / (stem + "_" + row["branch"] + "_" + row["selected_method"]) / "candidate.obj"
        if digest(candidate_path) != row["output_sha256"]:
            raise ValueError("特征审计实际输出摘要不一致")
        reference_row = next(item for item in record["rows"] if item["route"] == row["route"] and item["event"] == row["event"] and item["branch"] == "R")
        reference_root = Path(reference_row.get("source_output_directory", args.record.parent))
        reference_path = reference_root / (stem + "_reference") / reference_row.get("reference_used_file", "reference.obj")
        reference = trimesh.load(reference_path, process=True, validate=True)
        candidate = trimesh.load(candidate_path, process=False)
        for index, probe in enumerate(probes[row["route"]]):
            result = {"route": row["route"], "event": row["event"], "branch": row["branch"], "probe_index": index}
            try:
                a = material_intervals(reference, probe["axis"], probe["position_mm"])
                b = material_intervals(candidate, probe["axis"], probe["position_mm"])
                result.update(status="measured", **compare_intervals(a, b))
            except ValueError as error:
                result.update(status="unresolved", reason=str(error))
            rows.append(result)
    result = {"time_beijing": now(), "rows": rows, "measured": sum(row["status"] == "measured" for row in rows),
              "unresolved": sum(row["status"] == "unresolved" for row in rows), "scope": frozen["scope"]}
    result["branches"] = {}
    for branch in ("full", "candidate"):
        selected = [row for row in rows if row["branch"] == branch]
        measured = [row for row in selected if row["status"] == "measured"]
        summary = {"planned_queries": len(selected), "measured_queries": len(measured),
                   "unresolved_queries": len(selected)-len(measured),
                   "interval_count_mismatches": sum(not row["interval_count_matches"] for row in measured),
                   "central_void_presence_mismatches": sum(not row["central_void_presence_matches"] for row in measured)}
        for field in ("maximum_endpoint_difference_mm", "maximum_material_width_difference_mm", "central_void_width_difference_mm"):
            summary[field] = max((row[field] for row in measured if row[field] is not None), default=None)
        result["branches"][branch] = summary
    (args.output / "02-小特征扫描结果.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(result["measured"], result["unresolved"])


if __name__ == "__main__":
    main()
