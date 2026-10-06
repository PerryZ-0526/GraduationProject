"""在同来源、同活动分类的共面凸区域内改善对角线，不移动顶点。"""

import numpy as np
import trimesh
from locality_retriangulate import invalid_faces


def minimum_angles(vertices, faces):
    """返回每个三角形的最小角，单位为度。"""
    triangle = vertices[faces]
    angles = []
    for i in range(3):
        a = triangle[:, (i + 1) % 3] - triangle[:, i]
        b = triangle[:, (i + 2) % 3] - triangle[:, i]
        divisor = np.linalg.norm(a, axis=1) * np.linalg.norm(b, axis=1)
        cosine = np.divide(np.sum(a * b, axis=1), divisor, out=np.ones(len(faces)), where=divisor > 0)
        angles.append(np.degrees(np.arccos(np.clip(cosine, -1, 1))))
    return np.min(angles, axis=0)


def improve_planar(mesh, bits, active, max_flips=200):
    """有限预算单调改善局部最小角，三个小角阈值的面数均不得增加。"""
    bits, active = np.asarray(bits), np.asarray(active, dtype=bool)
    if len(bits) != len(mesh.faces) or len(active) != len(bits) or np.any(~np.isin(bits, [1, 2])):
        raise ValueError("平面维护的来源或活动域非法")
    vertices, faces = mesh.vertices.copy(), mesh.faces.copy()
    record = {"max_flips": max_flips, "plane_tolerance_mm": 1e-10, "flips": []}
    for _ in range(max_flips):
        current = trimesh.Trimesh(vertices, faces, process=False)
        angles = minimum_angles(vertices, faces)
        pairs = current.face_adjacency
        order = np.argsort(np.min(angles[pairs], axis=1), kind="stable")
        changed = False
        for index in order:
            i, j = map(int, pairs[index])
            if min(angles[i], angles[j]) >= 10:
                break
            if bits[i] != bits[j] or active[i] != active[j]:
                continue
            a, b = map(int, current.face_adjacency_edges[index])
            first, second = faces[i], faces[j]
            if not any(first[k] == a and first[(k + 1) % 3] == b for k in range(3)):
                a, b = b, a
            c = next(int(v) for v in first if v not in (a, b))
            d = next(int(v) for v in second if v not in (a, b))
            if c == d or np.any(np.sum(np.isin(faces, [c, d]), axis=1) == 2):
                continue
            replacement = np.array([[c, d, b], [d, c, a]])
            if invalid_faces(vertices, replacement).any():
                continue
            normal = np.cross(vertices[first[1]] - vertices[first[0]], vertices[first[2]] - vertices[first[0]])
            magnitude = np.linalg.norm(normal)
            if magnitude <= 2e-12:
                continue
            normal /= magnitude
            quad = vertices[[a, d, b, c]]
            if np.max(np.abs((quad - vertices[a]) @ normal)) > 1e-10:
                continue
            sides = np.roll(quad, -1, axis=0) - quad
            if np.any(np.cross(sides, np.roll(sides, -1, axis=0)) @ normal < -1e-14):
                continue
            triangles = vertices[replacement]
            normals = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
            if np.any(normals @ normal <= 2e-12):
                continue
            previous = angles[[i, j]]
            next_angles = minimum_angles(vertices, replacement)
            if next_angles.min() <= previous.min() + 1e-6:
                continue
            if any(np.count_nonzero(next_angles < threshold) > np.count_nonzero(previous < threshold) for threshold in (1, 5, 10)):
                continue
            faces[[i, j]] = replacement
            record["flips"].append({"faces": [i, j], "old_edge": [a, b], "new_edge": [c, d],
                                    "old_min_deg": float(previous.min()), "new_min_deg": float(next_angles.min()),
                                    "active": bool(active[i])})
            changed = True
            break
        if not changed:
            record["budget_exhausted"] = False
            break
    else:
        record["budget_exhausted"] = True
    record["vertices_exact"] = bool(np.array_equal(vertices, mesh.vertices))
    return trimesh.Trimesh(vertices, faces, process=False), record
