"""二进制坐标上闭线段间距离的有理数参照，不靠Gram差值浮点判定。"""
from fractions import Fraction
import math


def edge_edge_reference(values):
    """四端点按a、b、c、d输入，返回确定性最近特征编号和距离。"""
    a, b, c, d = [tuple(Fraction(float(x)) for x in point) for point in values]
    def sub(x, y):
        return tuple(u-v for u, v in zip(x, y))
    def dot(x, y):
        return sum(u*v for u, v in zip(x, y))
    candidates = []
    def point_segment(point, first, last, interior, first_kind, last_kind):
        direction = sub(last, first)
        denominator = dot(direction, direction)
        parameter = min(Fraction(1), max(Fraction(0), dot(sub(point, first), direction)/denominator)) if denominator else Fraction(0)
        delta = sub(point, tuple(x+parameter*y for x, y in zip(first, direction)))
        kind = first_kind if parameter == 0 else last_kind if parameter == 1 else interior
        candidates.append((dot(delta, delta), kind))
    point_segment(a, c, d, 4, 0, 1)
    point_segment(b, c, d, 5, 2, 3)
    point_segment(c, a, b, 6, 0, 2)
    point_segment(d, a, b, 7, 1, 3)
    # 内部驻点仅在精确非平行且两参数落在闭线段内部时成为候选。
    r, s, w = sub(b, a), sub(d, c), sub(a, c)
    rr, rs, ss, rw, sw = dot(r, r), dot(r, s), dot(s, s), dot(r, w), dot(s, w)
    determinant = rr*ss-rs*rs
    if determinant > 0:
        first = (rs*sw-ss*rw)/determinant
        second = (rr*sw-rs*rw)/determinant
        if 0 < first < 1 and 0 < second < 1:
            delta = tuple(x+first*y-second*z for x, y, z in zip(w, r, s))
            candidates.append((dot(delta, delta), 8))
    square, kind = min(candidates, key=lambda item: item[0])
    return kind, math.sqrt(float(square))
