"""用凸投影公共细分给出翻边前后连续面片的双向距离上界。"""
from fractions import Fraction
import numpy as np


def cross2(a, b):
    return a[0] * b[1] - a[1] * b[0]


def difference(a, b):
    return tuple(x - y for x, y in zip(a, b))


def patch_bound(vertices, old_edge, new_edge):
    a, b, c, d = [[Fraction(float(x)) for x in vertices[i]] for i in (*old_edge, *new_edge)]
    points = np.asarray(vertices)[list((*old_edge, *new_edge))]
    normals = [np.cross(points[1] - points[0], points[j] - points[0]) for j in (2, 3)]
    normal = max(normals, key=lambda n: np.linalg.norm(n))
    # 依稳定面法线选择投影轴；只有精确凸性和内部交点成立的轴才能给证书。
    for axis in np.argsort(-np.abs(normal)):
        axis = int(axis)
        keep = [j for j in range(3) if j != axis]
        projected = [tuple(point[j] for j in keep) for point in (a, d, b, c)]
        sides = [difference(projected[(i + 1) % 4], projected[i]) for i in range(4)]
        turns = [cross2(sides[i], sides[(i + 1) % 4]) for i in range(4)]
        if not (all(x > 0 for x in turns) or all(x < 0 for x in turns)):
            continue
        pa, pd, pb, pc = projected
        u, v, w = difference(pb, pa), difference(pd, pc), difference(pc, pa)
        determinant = cross2(u, v)
        if determinant == 0:
            continue
        s, t = cross2(w, v) / determinant, cross2(w, u) / determinant
        if not (0 < s < 1 and 0 < t < 1):
            continue
        old_height = a[axis] + s * (b[axis] - a[axis])
        new_height = c[axis] + t * (d[axis] - c[axis])
        bound = abs(old_height - new_height)
        # 两个连续面片是同一凸投影域上的分段线性图，差值极值仅在对角线交点出现。
        return {'certified': True, 'projection_axis': axis, 'old_parameter': str(s), 'new_parameter': str(t),
                'bidirectional_bound_mm_fraction': str(bound), 'bidirectional_bound_mm': float(bound)}
    return {'certified': False, 'reason': '无严格凸投影及内部对角线交点'}


def finite_controls():
    planar = np.array([[-1., 0, 0], [1., 0, 0], [0, -1., 0], [0, 1., 0]])
    nonplanar = planar.copy()
    nonplanar[3, 2] = 1
    nonconvex = planar.copy()
    nonconvex[3, 1] = -.5
    rows = [patch_bound(points, [0, 1], [2, 3]) for points in (planar, nonplanar, nonconvex)]
    passed = (rows[0]['certified'] and Fraction(rows[0]['bidirectional_bound_mm_fraction']) == 0
              and rows[1]['certified'] and Fraction(rows[1]['bidirectional_bound_mm_fraction']) == Fraction(1, 2)
              and not rows[2]['certified'])
    return {'passed': bool(passed), 'controls': rows, 'scope': '三项有限解析面片控制，非形式验证'}
