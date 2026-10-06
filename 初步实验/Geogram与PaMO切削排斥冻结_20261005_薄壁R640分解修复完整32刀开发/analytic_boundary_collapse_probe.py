"""对解析箱体侧面和其上方平面交线邻域的指定边试行折叠。"""

import argparse
import json
from pathlib import Path

import numpy as np
import trimesh

from short_edge_collapse_probe import quality, topology_maps


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--diagnostics", type=Path, required=True)
    parser.add_argument("--operation", nargs=3, action="append", required=True,
                        metavar=("保留顶点", "删除顶点", "位置规则"))
    args = parser.parse_args()
    mesh = trimesh.load(args.input, force="mesh", process=False)
    vertices = np.asarray(mesh.vertices, dtype=np.float64).copy()
    faces = np.asarray(mesh.faces, dtype=np.int64).copy()
    accepted = []
    for first_text, second_text, mode in args.operation:
        first, second = int(first_text), int(second_text)
        incident, neighbors = topology_maps(faces)
        common = incident[first] & incident[second]
        opposite = {int(vertex) for face_id in common for vertex in faces[face_id]
                    if vertex not in (first, second)}
        if (len(common) != 2 or len(opposite) != 2
                or neighbors[first] & neighbors[second] != opposite):
            raise ValueError(f"边{first, second}不满足双面及链接条件")
        affected = sorted(incident[first] | incident[second])
        retained = [face_id for face_id in affected if face_id not in common]
        old_bad, old_normals, _ = quality(vertices, faces[affected])
        replacement = faces[retained].copy()
        replacement[replacement == second] = first
        if np.any(np.diff(np.sort(replacement, axis=1), axis=1) == 0):
            raise ValueError("折叠产生退化面")
        midpoint = (vertices[first] + vertices[second]) / 2
        if mode == "y_line":
            position = np.array([midpoint[0], -2.0, 0.15 * midpoint[0] + 0.2])
            near_side = np.max(np.abs(vertices[[first, second], 1] + 2)) <= 0.03
        elif mode == "x_side":
            position = np.array([2.0, midpoint[1], midpoint[2]])
            near_side = np.max(np.abs(vertices[[first, second], 0] - 2)) <= 0.03
        elif mode == "keep_y":
            position = vertices[first].copy()
            near_side = np.max(np.abs(vertices[[first, second], 1] + 2)) <= 0.03
        else:
            raise ValueError("未定义的位置规则")
        # 仅合并靠近解析侧面的短边，且限制新旧顶点的最大位移。
        distances = np.linalg.norm(vertices[[first, second]] - position, axis=1)
        if (not near_side or np.linalg.norm(vertices[first] - vertices[second]) > 0.05
                or max(distances) > 0.03):
            raise ValueError("候选边未贴近解析侧面或移动过大")
        proposed = vertices.copy()
        proposed[first] = position
        new_bad, new_normals, new_angles = quality(proposed, replacement)
        old_retained_normals = old_normals[np.isin(affected, retained)]
        old_retained_bad = old_bad[np.isin(affected, retained)]
        if (int(new_bad.sum()) >= int(old_bad.sum())
                or np.any(new_bad & ~old_retained_bad)
                or np.any(new_angles[~new_bad] < 25.1)
                or np.any(np.einsum("ij,ij->i", new_normals, old_retained_normals) <= 0.9)):
            raise ValueError("折叠未满足局部质量及法向约束")
        vertices[first] = position
        faces[faces == second] = first
        faces = np.delete(faces, sorted(common), axis=0)
        accepted.append({"edge": [first, second], "position_rule": mode,
                         "position": position.tolist(),
                         "max_vertex_move_mm": float(max(distances)),
                         "local_bad_before": int(old_bad.sum()),
                         "local_bad_after": int(new_bad.sum()),
                         "local_min_angle_deg": float(min(new_angles))})
    result = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    result.remove_unreferenced_vertices()
    args.output.write_text(trimesh.exchange.obj.export_obj(result, digits=17), encoding="utf-8")
    args.diagnostics.write_text(json.dumps({
        "input": str(args.input), "output": str(args.output), "accepted": accepted,
        "final_bad_faces": int(quality(np.asarray(result.vertices), np.asarray(result.faces))[0].sum()),
    }, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
