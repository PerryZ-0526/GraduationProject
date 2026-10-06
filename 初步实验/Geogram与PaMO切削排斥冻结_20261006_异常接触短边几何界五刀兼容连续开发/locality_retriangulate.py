"""用同来源近共面翻边消除数值退化面；不移动顶点，不恢复旧质量翻边假设。"""

import numpy as np
import trimesh


def invalid_faces(vertices, faces):
    """同时检查输入FP64与PaMO实际FP32坐标的退化面积。"""
    result = np.zeros(len(faces), dtype=bool)
    for coordinates in (vertices, vertices.astype(np.float32).astype(np.float64)):
        triangles = coordinates[faces]
        area2 = np.linalg.norm(np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0]), axis=1)
        result |= area2 <= 2e-12
    return result


def repair_degenerate(mesh, bits, allow_shared=False, candidate_guard=None):
    """每次翻边必须减少退化面；预算为初始退化面数，不能按结果追加轮数。"""
    bits = np.asarray(bits)
    # 共同来源须显式开启，翻边仍只能在完全相同来源标签之间进行。
    if len(bits) != len(mesh.faces) or np.any(~np.isin(bits, [1, 2, 3] if allow_shared else [1, 2])):
        raise ValueError("来源缺失或多义，禁止重三角化")
    vertices, faces = mesh.vertices.copy(), mesh.faces.copy()
    initial_bad = int(invalid_faces(vertices, faces).sum())
    record = {"initial_invalid_faces": initial_bad, "max_flips": initial_bad,
              "plane_tolerance_mm": 1e-8, "area_threshold_mm2": 1e-12, "flips": [],
              "rejected_pair_checks": {},
              "scope": "数值近共面与凸性测试，非精确谓词或连续几何证书"}
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
            if deviation > 1e-8:
                reject("nonplanar")
                continue
            # 共面凸四边形含共线边界点可换对角线；凹四边形不能填补原面外区域。
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
            # 提交前核对实际父面和工具面，逐次平面偏差通过仍不能替代累计来源核对。
            if candidate_guard is not None:
                proposed_faces = faces.copy()
                proposed_faces[[i, j]] = replacement
                proposed = trimesh.Trimesh(vertices, proposed_faces, process=False)
                if not candidate_guard(proposed, bits):
                    reject("parent_and_tool_provenance_guard")
                    continue
            faces[[i, j]] = replacement
            record["flips"].append({"faces": [i, j], "old_edge": [a, b], "new_edge": [c, d],
                                    "source_bit": int(bits[i]), "plane_deviation_mm": deviation})
            repaired = True
            break
        if not repaired:
            break
    result = trimesh.Trimesh(vertices, faces, process=False)
    record["remaining_invalid_faces"] = int(invalid_faces(vertices, faces).sum())
    record["vertices_exact"] = bool(np.array_equal(vertices, mesh.vertices))
    return result, bits.copy(), record
