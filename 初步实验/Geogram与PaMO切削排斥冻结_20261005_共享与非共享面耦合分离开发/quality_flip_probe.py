"""在冻结网格上试验保特征的局部质量约束边翻转。"""

import argparse
import json
from pathlib import Path

import numpy as np
import trimesh


def face_values(vertices, triangle):
    points = vertices[triangle]
    vectors = np.roll(points, -1, axis=0) - points
    lengths = np.linalg.norm(vectors, axis=1)
    area2 = np.linalg.norm(np.cross(points[1] - points[0], points[2] - points[0]))
    q = 2 * np.sqrt(3) * area2 / np.sum(lengths**2)
    angles = []
    for corner in range(3):
        u = -vectors[corner - 1]
        v = vectors[corner]
        cosine = np.dot(u, v) / (np.linalg.norm(u) * np.linalg.norm(v))
        angles.append(np.degrees(np.arccos(np.clip(cosine, -1, 1))))
    angle = min(angles)
    normal = np.cross(points[1] - points[0], points[2] - points[0]) / area2
    return area2 / 2, q, angle, normal


def edges(triangle):
    return [tuple(sorted((int(triangle[i]), int(triangle[(i + 1) % 3]))))
            for i in range(3)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--diagnostics", required=True, type=Path)
    args = parser.parse_args()
    mesh = trimesh.load(args.input, force="mesh", process=False)
    vertices = np.asarray(mesh.vertices, dtype=np.float64)
    faces = np.asarray(mesh.faces, dtype=np.int64).copy()
    incident = {}
    for face_id, triangle in enumerate(faces):
        for edge in edges(triangle):
            incident.setdefault(edge, set()).add(face_id)
    accepted_by_pass = []
    for _ in range(5):
        accepted = 0
        for shared in sorted(incident):
            owners = incident.get(shared, set())
            if len(owners) != 2:
                continue
            first_id, second_id = sorted(owners)
            first, second = faces[first_id], faces[second_id]
            a, b = shared
            if not any(first[i] == a and first[(i + 1) % 3] == b
                       for i in range(3)):
                a, b = b, a
            c = next(int(v) for v in first if v not in shared)
            d = next(int(v) for v in second if v not in shared)
            if c == d or tuple(sorted((c, d))) in incident:
                continue
            before = [face_values(vertices, first), face_values(vertices, second)]
            if all(area > 1e-12 and q >= 0.4 and angle >= 25
                   for area, q, angle, _ in before):
                continue
            if np.dot(before[0][3], before[1][3]) < np.cos(np.deg2rad(30)):
                continue
            old_normal = before[0][3] + before[1][3]
            old_normal /= np.linalg.norm(old_normal)
            # 只翻转近共面四边形，限制新旧局部曲面的偏离。
            if max(abs(np.dot(vertices[c] - vertices[a], before[1][3])),
                   abs(np.dot(vertices[d] - vertices[a], before[0][3]))) > 0.005:
                continue
            replacement = [np.array([c, d, b]), np.array([d, c, a])]
            after = [face_values(vertices, triangle) for triangle in replacement]
            if any(area <= 1e-12 or np.dot(normal, old_normal) <= 0
                   for area, _, _, normal in after):
                continue
            old_bad = sum(area <= 1e-12 or q < 0.4 or angle < 25
                          for area, q, angle, _ in before)
            new_bad = sum(area <= 1e-12 or q < 0.4 or angle < 25
                          for area, q, angle, _ in after)
            if new_bad > old_bad or (new_bad == old_bad and
                                    min(item[2] for item in after)
                                    <= min(item[2] for item in before) + 1):
                continue
            for face_id, old_triangle in ((first_id, first), (second_id, second)):
                for edge in edges(old_triangle):
                    incident[edge].remove(face_id)
                    if not incident[edge]:
                        del incident[edge]
            for face_id, new_triangle in zip((first_id, second_id), replacement):
                faces[face_id] = new_triangle
                for edge in edges(new_triangle):
                    incident.setdefault(edge, set()).add(face_id)
            accepted += 1
        accepted_by_pass.append(accepted)
        if not accepted:
            break
    output = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    output.export(args.output)
    args.diagnostics.write_text(json.dumps({
        "input": str(args.input),
        "output": str(args.output),
        "accepted_flips_by_pass": accepted_by_pass,
        "face_count": len(faces),
        "operation": "局部近共面、非特征双面边翻转；无顶点移动",
    }, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
