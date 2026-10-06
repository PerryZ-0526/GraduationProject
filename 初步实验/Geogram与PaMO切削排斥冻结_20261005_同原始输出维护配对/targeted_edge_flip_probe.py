"""对预先指定的非特征内边实施一次受约束翻边。"""

import argparse
import json
from pathlib import Path

import numpy as np
import trimesh

from quality_flip_probe import edges, face_values


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--diagnostics", type=Path, required=True)
    parser.add_argument("--edge", nargs=2, type=int, required=True)
    args = parser.parse_args()
    mesh = trimesh.load(args.input, force="mesh", process=False)
    vertices = np.asarray(mesh.vertices, dtype=np.float64)
    faces = np.asarray(mesh.faces, dtype=np.int64).copy()
    shared = tuple(sorted(int(v) for v in args.edge))
    owners = [int(i) for i, face in enumerate(faces) if shared in edges(face)]
    if len(owners) != 2:
        raise ValueError("指定边不是双面共享的内边")
    first, second = (faces[i] for i in owners)
    a, b = shared
    if not any(first[i] == a and first[(i + 1) % 3] == b for i in range(3)):
        a, b = b, a
    c = next(int(v) for v in first if v not in shared)
    d = next(int(v) for v in second if v not in shared)
    if any(tuple(sorted((c, d))) in edges(face) for face in faces):
        raise ValueError("新对角线已经存在")
    before = [face_values(vertices, first), face_values(vertices, second)]
    dihedral = np.degrees(np.arccos(np.clip(np.dot(before[0][3], before[1][3]), -1, 1)))
    if dihedral > 30:
        raise ValueError("指定边可能是需保留的锐边")
    # 仅允许局部质量严格改善，且新面留有角度余量。
    replacement = [np.array([c, d, b]), np.array([d, c, a])]
    after = [face_values(vertices, face) for face in replacement]
    old_bad = sum(area <= 1e-12 or q < 0.4 or angle < 25 for area, q, angle, _ in before)
    new_bad = sum(area <= 1e-12 or q < 0.4 or angle < 25 for area, q, angle, _ in after)
    deviation = max(abs(np.dot(vertices[c] - vertices[a], before[1][3])),
                    abs(np.dot(vertices[d] - vertices[a], before[0][3])))
    if (new_bad >= old_bad or any(area <= 1e-12 or q < 0.4 or angle < 25.1
                                  for area, q, angle, _ in after)
            or deviation > 0.015
            or any(np.dot(new[3], old[3]) <= 0.9 for new in after for old in before)):
        raise ValueError("翻边未满足局部质量、法向或偏差约束")
    for face_id, face in zip(owners, replacement):
        faces[face_id] = face
    output = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    args.output.write_text(trimesh.exchange.obj.export_obj(output, digits=17), encoding="utf-8")
    # 将 NumPy 标量转为普通数值，确保操作证据可写入 JSON。
    args.diagnostics.write_text(json.dumps({
        "input": str(args.input), "output": str(args.output),
        "edge": shared, "faces": owners, "new_edge": tuple(sorted((c, d))),
        "dihedral_deg": float(dihedral), "local_bad_before": int(old_bad),
        "local_bad_after": int(new_bad), "local_plane_deviation_mm": float(deviation),
        "new_min_angle_deg": float(min(item[2] for item in after)),
        "new_min_q": float(min(item[1] for item in after)),
    }, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
