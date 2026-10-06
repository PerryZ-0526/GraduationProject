from fractions import Fraction
from flip_patch_geometry_bound import patch_bound
"""用同来源精确变化界翻边消除低面积面，保持顶点和既有1e-7毫米变化预算。"""

import numpy as np
import trimesh


def invalid_faces(vertices, faces):
    """仅检查保存FP64物理面积；编码退化仍由固定几何后端独立审查。"""
    result = np.zeros(len(faces), dtype=bool)
    for coordinates in (vertices,):
        triangles = coordinates[faces]
        area2 = np.linalg.norm(np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0]), axis=1)
        result |= area2 <= 2e-12
    return result


def repair_degenerate(mesh, bits, allow_shared=False):
    """每次翻边必须减少退化面；预算为初始退化面数，不能按结果追加轮数。"""
    bits = np.asarray(bits)
    # 共同来源须显式开启，翻边仍只能在完全相同来源标签之间进行。
    if len(bits) != len(mesh.faces) or np.any(~np.isin(bits, [1, 2, 3] if allow_shared else [1, 2])):
        raise ValueError("来源缺失或多义，禁止重三角化")
    vertices, faces = mesh.vertices.copy(), mesh.faces.copy()
    initial_bad = int(invalid_faces(vertices, faces).sum())
    record = {"initial_invalid_faces": initial_bad, "max_flips": initial_bad,
              "plane_tolerance_mm": None, "continuous_change_budget_mm": 1e-7, "area_threshold_mm2": 1e-12, "flips": [],
              "rejected_pair_checks": {},
              "scope": "精确凸投影与源到修复连续变化上界；整体输出仍须独立嵌入和拓扑复审"}
    def reject(reason):
        record["rejected_pair_checks"][reason] = record["rejected_pair_checks"].get(reason, 0) + 1
    for _ in range(initial_bad):
        bad = invalid_faces(vertices, faces)
        candidate = trimesh.Trimesh(vertices, faces, process=False)
        repaired = False
        for owners, edge in zip(candidate.face_adjacency, candidate.face_adjacency_edges):
            i, j = map(int, owners)
            if not (bad[i] or bad[j]):
                continue
            if bits[i] != bits[j]:
                reject("different_source")
                continue
            a, b = map(int, edge)
            first, second = faces[i], faces[j]
            if not any(first[k] == a and first[(k + 1) % 3] == b for k in range(3)):
                a, b = b, a
            c = next(int(v) for v in first if v not in (a, b))
            d = next(int(v) for v in second if v not in (a, b))
            if c == d or not any(second[k] == b and second[(k + 1) % 3] == a for k in range(3)):
                reject("invalid_local_link")
                continue
            if np.any(np.sum(np.isin(faces, [c, d]), axis=1) == 2):
                reject("diagonal_exists")
                continue
            replacement = np.array([[c, d, b], [d, c, a]])
            if invalid_faces(vertices, replacement).any():
                reject("new_invalid_face")
                continue
            old = vertices[faces[[i, j]]]
            normals = np.cross(old[:, 1] - old[:, 0], old[:, 2] - old[:, 0])
            normal = normals[np.argmax(np.linalg.norm(normals, axis=1))]
            length = np.linalg.norm(normal)
            if length <= 2e-12:
                reject("no_stable_support_plane")
                continue
            normal /= length
            quad = vertices[[a, d, b, c]]
            deviation = float(np.max(np.abs((quad - vertices[a]) @ normal)))
            # 用同一1e-7毫米连续面片变化预算选择翻边，不再用共面距离代替实际变化界。
            certificate = patch_bound(vertices, [a, b], [c, d])
            if not certificate.get("certified"):
                reject("no_exact_convex_projection")
                continue
            proposed = Fraction(certificate["bidirectional_bound_mm_fraction"])
            used = sum((Fraction(row["exact_change_bound"]["bidirectional_bound_mm_fraction"]) for row in record["flips"]), Fraction(0))
            if used + proposed > Fraction(1, 10000000):
                reject("continuous_change_budget")
                continue
            # 保留旧浮点方向筛查；严格凸投影和内部对角线交点已由精确有理数核查。
            sides = np.roll(quad, -1, axis=0) - quad
            turns = np.cross(sides, np.roll(sides, -1, axis=0)) @ normal
            slack = 1e-14 * max(float(np.sum(sides * sides)), 1e-12)
            if np.any(turns < -slack):
                reject("nonconvex")
                continue
            new = vertices[replacement]
            new_normals = np.cross(new[:, 1] - new[:, 0], new[:, 2] - new[:, 0])
            if np.any(new_normals @ normal <= 2e-12):
                reject("orientation_or_projected_area")
                continue
            faces[[i, j]] = replacement
            record["flips"].append({"faces": [i, j], "old_edge": [a, b], "new_edge": [c, d],
                                    "source_bit": int(bits[i]), "plane_deviation_mm": deviation, "exact_change_bound": certificate})
            repaired = True
            break
        if not repaired:
            break
    result = trimesh.Trimesh(vertices, faces, process=False)
    record["remaining_invalid_faces"] = int(invalid_faces(vertices, faces).sum())
    record["vertices_exact"] = bool(np.array_equal(vertices, mesh.vertices))
    return result, bits.copy(), record
