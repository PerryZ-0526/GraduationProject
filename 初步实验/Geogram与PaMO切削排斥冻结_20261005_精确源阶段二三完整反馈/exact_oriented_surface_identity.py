"""严格比较保存坐标的有向三角面重数，识别布尔无变化而不使用距离容差。"""
from collections import Counter
import numpy as np


def exact_oriented_surface_identity(parent, source, source_bits):
    bits = np.asarray(source_bits)
    if len(bits) != len(source.faces) or not np.all(bits == 1):
        return {'same': False, 'reason': 'source_contains_non_parent_faces_or_invalid_labels'}
    if not np.isfinite(parent.vertices).all() or not np.isfinite(source.vertices).all():
        return {'same': False, 'reason': 'nonfinite_coordinates'}

    def chain(mesh):
        result = Counter()
        for triangle in np.asarray(mesh.vertices, np.float64)[mesh.faces]:
            points = tuple(tuple(float(x) for x in vertex) for vertex in triangle)
            # 只消除有向面的循环起点差异，反向面和面重数必须区分。
            key = min(points, points[1:] + points[:1], points[2:] + points[:2])
            result[key] += 1
        return result

    first, second = chain(parent), chain(source)
    return {'same': first == second, 'reason': 'exact_parent_only_oriented_triangle_multiset',
            'parent_faces': len(parent.faces), 'source_faces': len(source.faces),
            'missing_parent_face_occurrences': sum((first - second).values()),
            'extra_source_face_occurrences': sum((second - first).values()),
            'coordinate_tolerance_mm': None, 'source_labels_all_parent': True}
