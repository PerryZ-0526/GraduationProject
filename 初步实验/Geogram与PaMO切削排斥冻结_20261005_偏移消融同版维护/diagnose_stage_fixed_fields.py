"""在相同初态探针上比较指定事件的源、完整GPU阶段和最终维护输出。"""

import argparse
import json
from pathlib import Path

import numpy as np
import trimesh
import run_reference_cut_feedback
from audit_followup_candidate import sha256
from audit_pamo_outputs import as_polydata
from geometry_preservation_audit import MeshDistance
from geometry_error_distribution import distance_distribution
from run_geometry_study import now, save


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("batch", "prepared", "stages", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    batch_path = args.batch / "01-统一配置完整父反馈记录.json"
    batch = json.loads(batch_path.read_text("utf8"))
    stage_path = args.stages / "01-简化邻接顺序同输入完整对照.json"
    stages = json.loads(stage_path.read_text("utf8"))
    manifest_path = args.prepared / "01-完整范围冻结清单.json"
    manifest = json.loads(manifest_path.read_text("utf8"))
    if stages["status"] != "completed" or stages["previous_record_sha256"] != sha256(batch_path):
        raise ValueError("要求同一原终态记录的完整阶段观察")
    if batch["manifest_sha256"] != sha256(manifest_path):
        raise ValueError("输入清单摘要不同")
    route = next(row for row in manifest["routes"] if row["id"] == batch["selected_route"])
    event = next(row for row in batch["rows"] if row["event"] == stages["selected_event"])
    stem = route["id"] + "_" + event["event"]
    initial = args.prepared / "inputs" / route["initial_mesh"]
    reference = args.batch / (stem + "_reference") / "validated_reference.obj"
    if not reference.exists():
        reference = reference.with_name("reference.obj")
    source = args.batch / (stem + "_candidate_input") / "clean_source.obj"
    raw = args.batch / (stem + "_candidate_boolean") / "raw_full_candidate.obj"
    final = raw.with_name("candidate.obj")
    expected = {initial: route["initial_mesh_sha256"], reference: event["reference_sha256"],
                source: event["attempt"]["inputs_sha256"]["source.obj"],
                raw: event["attempt"]["raw_full_output_sha256"], final: event["output_sha256"]}
    for path, digest in expected.items():
        if sha256(path) != digest:
            raise ValueError("实际诊断对象摘要不同：" + str(path))
    points = trimesh.load(initial, force="mesh", process=False).vertices
    reference_distances = MeshDistance(as_polydata(trimesh.load(reference, force="mesh", process=True)))(points)
    args.output.mkdir(exist_ok=False)
    report = {"生成时间": now(), "修改时间及修改内容": "首次生成，同探针阶段定位",
              "文档概述": "固定初态点到各阶段与累计参照的无符号距离场差异，阶段观察带额外同步，不能用于计时",
              "索引目录": ["rows"], "batch_sha256": sha256(batch_path), "stage_record_sha256": sha256(stage_path),
              "event": event["event"], "initial_sha256": sha256(initial), "reference_sha256": sha256(reference),
              "fixed_probe_count": len(points), "area_weighted": False, "new_GPU_calls": 0, "rows": []}
    objects = [("actual_source", source), ("original_raw_GPU", raw), ("final_maintenance", final)]
    for index, run in enumerate(stages["rows"], 1):
        for stage in ("stage1", "stage2", "stage3"):
            path = args.stages / f"同输入GPU第{index}次" / "阶段观测" / (stage + ".obj")
            if sha256(path) != run["stage_observations"][stage]["sha256"]:
                raise ValueError("实际阶段保存对象摘要不符")
            objects.append((f"repeat{index}_{stage}", path))
    for name, path in objects:
        distances = MeshDistance(as_polydata(trimesh.load(path, force="mesh", process=False)))(points)
        delta = np.abs(distances - reference_distances)
        worst = int(delta.argmax())
        # 相同探针用于定位阶段变化，0.1毫米仅为尾部参考档位，不决定质量接受。
        report["rows"].append({"name": name, "sha256": sha256(path), "distance_field_difference": distance_distribution(delta),
            "worst_initial_vertex_id": worst, "worst_position_mm": points[worst].tolist(),
            "reference_distance_at_worst_mm": float(reference_distances[worst]), "object_distance_at_worst_mm": float(distances[worst]),
            "tail_initial_vertex_ids": np.flatnonzero(delta > .1).tolist()})
        print(name, "maximum_field_difference", float(delta[worst]), flush=True)
    save(args.output / "01-同初态探针完整阶段距离场诊断.json", report)


if __name__ == "__main__":
    main()
