"""保留公开骨模型原件，生成明确测试尺度的派生网格与局部仿真磨削。"""

from datetime import datetime, timezone, timedelta
import argparse
import json
from pathlib import Path
import numpy as np
import trimesh
from prepare_feedback import HERE, digest, make_route, save_obj_fp64


def main(output):
    source_root = HERE / "公开输入_BodyParts3D_v4"
    source_manifest = source_root / "01-公开来源清单.json"
    manifest = json.loads(source_manifest.read_text(encoding="utf-8"))
    names = {"right scapula", "left scapula", "right humerus", "left humerus", "right femur", "left femur", "right tibia", "left tibia"}
    # 原提取清单按文件去重，首次映射可能是骨的子结构；重新读取完整骨的官方映射。
    models = {row["id"]: row for row in manifest["models"]}
    selected = []
    for line in (source_root / "原始资料/isa_element_parts.txt").read_text(encoding="utf-8-sig").splitlines():
        fields = line.split("\t")
        if len(fields) == 3 and fields[1] in names:
            selected.append({**models[fields[2]], "mapping_line": line})
    if len(selected) != 8:
        raise ValueError("完整骨映射不是预定八件，禁止静默换数据")
    inputs = output / "inputs"
    inputs.mkdir(parents=True, exist_ok=False)
    report = {"time_beijing": datetime.now(timezone(timedelta(hours=8))).isoformat(), "source_manifest_sha256": digest(source_manifest),
              "generator_sha256": digest(Path(__file__)), "routes": [], "derivatives": [], "negative_inputs": [],
              "scope": "单个解剖图谱八个骨模型，非独立患者或真实磨削；全部用于公开应用开发",
              "replay_policy": {"late_event": "reject", "max_link_gap_ms": 200},
              "units": {"length": "mm_explicit_test_scale", "time": "ms"}}
    for row in selected:
        path = source_root / row["file"]
        if digest(path) != row["sha256"]:
            raise ValueError("公开原件摘要改变")
        mesh = trimesh.load(path, force="mesh", process=False)
        # 只合并逐位相同的坐标，不用小数舍入，也不填孔洞；记录原件拓扑差异。
        before_vertices = len(mesh.vertices)
        unique, inverse = np.unique(mesh.vertices, axis=0, return_inverse=True)
        mesh = trimesh.Trimesh(unique, inverse[mesh.faces], process=False)
        center = mesh.bounds.mean(axis=0)
        scale = 100 / float(mesh.extents.max())
        mesh.vertices = (mesh.vertices - center) * scale
        body = {"id": "BP3D_" + row["id"]}
        initial = inputs / (body["id"] + ".obj")
        save_obj_fp64(mesh, initial)
        # 选择最大原始三角面的中心；轨迹在其切平面内小范围运动，不挑维护结果。
        face_id = int(np.argmax(mesh.area_faces))
        normal = mesh.face_normals[face_id]
        point = mesh.triangles_center[face_id] + normal * 0.7
        tangent = mesh.triangles[face_id, 1] - mesh.triangles[face_id, 0]
        tangent /= np.linalg.norm(tangent)
        bitangent = np.cross(normal, tangent)
        for name, turns, count in (("交叉浅磨", 1, 5), ("重复长磨", 3, 25)):
            t = np.linspace(0, turns * 2 * np.pi, count)
            points = point + 0.5 * np.cos(t)[:, None] * tangent + 0.5 * np.sin(t)[:, None] * bitangent
            motion = {"tool_radius_mm": 1.0, "events": [{"position_mm": p.tolist()} for p in points]}
            report["routes"].append(make_route(body, name, motion, initial, inputs, "application", "public_atlas_test_scale"))
        report["derivatives"].append({"id": body["id"], "organ_mapping": row["mapping_line"], "original_sha256": row["sha256"],
                                     "derived_sha256": digest(initial), "translate_before_scale": (-center).tolist(), "scale": scale,
                                     "maximum_extent_test_mm": 100, "units_note": "人为测试尺度，不是恢复解剖真实毫米",
                                     "repair": "逐位相同坐标去重后坐标变换；没有补洞或重网格",
                                     "exact_weld": {"before_vertices": before_vertices, "after_vertices": len(unique), "coordinate_movement_mm": 0},
                                     "initial_watertight": bool(mesh.is_watertight),
                                     "initial_winding_consistent": bool(mesh.is_winding_consistent), "initial_faces": len(mesh.faces),
                                     "cut_anchor_source_face": face_id})
    (output / "01-完整范围冻结清单.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"bodies": len(selected), "routes": len(report["routes"]),
                      "prefixes": sum(len(r["cutting_prefix_ids"]) for r in report["routes"])}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=HERE / "公开骨面连续输入_v2_精确去重")
    main(parser.parse_args().output)
