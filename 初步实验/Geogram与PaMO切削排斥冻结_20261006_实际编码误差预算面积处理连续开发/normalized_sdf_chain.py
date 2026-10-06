"""归一化FP32三角面的精确有向面链整理，不使用几何容差。"""

from collections import Counter
import numpy as np


def canonical_normalized_chain(triangles):
    triangles = np.asarray(triangles)
    if triangles.ndim != 3 or triangles.shape[1:] != (3, 3) or not np.isfinite(triangles).all():
        raise ValueError("归一化三角面维度或有限性错误")
    vertices, inverse = np.unique(triangles.reshape(-1, 3), axis=0, return_inverse=True)
    faces = inverse.reshape(-1, 3)
    weights, representatives, occurrences = Counter(), {}, Counter()
    zeros = 0
    for face in faces:
        if len(set(map(int, face))) != 3:
            # 仅移除已完全塌成边或点的零面链，不按面积阈值删除正面积面。
            zeros += 1
            continue
        key = tuple(sorted(map(int, face)))
        sign = 1 if sum(int(face[i]) > int(face[j]) for i in range(3) for j in range(i + 1, 3)) % 2 == 0 else -1
        weights[key] += sign
        occurrences[key] += 1
        representatives[(key, sign)] = face
    if any(abs(weight) > 1 for weight in weights.values()):
        raise ValueError("同向重复面有非单位重数，不能按闭合单层表面整理")
    kept = np.asarray([representatives[(key, int(weight))] for key, weight in weights.items() if weight], dtype=np.int64)
    if len(kept) == 0:
        raise ValueError("有向面链为空，不能生成SDF")
    after = Counter()
    for face in kept:
        key = tuple(sorted(map(int, face)))
        sign = 1 if sum(int(face[i]) > int(face[j]) for i in range(3) for j in range(i + 1, 3)) % 2 == 0 else -1
        after[key] += sign
    before = {key: weight for key, weight in weights.items() if weight}
    if dict(after) != before:
        raise ValueError("精确有向面系数没有保持")
    cleaned = np.ascontiguousarray(vertices[kept])
    report = {"input_faces": len(faces), "output_faces": len(kept), "exact_coordinate_welding": True,
              "zero_repeated_index_faces_removed": zeros,
              "opposite_face_pairs_cancelled": sum((occurrences[key] - abs(weight)) // 2 for key, weight in weights.items()),
              "directed_triangle_coefficients_preserved": True, "unoriented_surface_union_identity_claimed": False,
              "actual_collision_source_modified": False, "geometry_tolerance": None,
              "unchanged_triangle_array": np.array_equal(cleaned, triangles)}
    return vertices, kept, cleaned, report
