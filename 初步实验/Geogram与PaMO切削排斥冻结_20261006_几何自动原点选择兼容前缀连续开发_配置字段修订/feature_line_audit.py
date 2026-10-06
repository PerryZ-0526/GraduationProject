"""沿固定坐标轴扫描闭合实体的材料区间，显式拒绝边界及相切歧义。"""
from fractions import Fraction
import numpy as np


def vector(values):
    return tuple(Fraction(float(value)) for value in values)


def subtract(a, b):
    return tuple(x - y for x, y in zip(a, b))


def cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


def dot(a, b):
    return sum(x*y for x, y in zip(a, b))


def material_intervals(mesh, axis, position):
    """对输入二进制坐标作有理数面相交，返回有限扫描线上的材料区间。"""
    if axis not in (0, 1, 2):
        raise ValueError("扫描轴必须为0、1、2")
    if not mesh.is_watertight or not mesh.is_winding_consistent:
        raise ValueError("扫描实体不闭合或绕序不一致")
    if not np.isfinite(mesh.vertices).all() or not np.isfinite(position).all():
        raise ValueError("扫描输入非有限")
    perpendicular = [index for index in range(3) if index != axis]
    triangles = mesh.triangles
    selected = np.ones(len(triangles), dtype=bool)
    for index in perpendicular:
        selected &= (triangles[:, :, index].min(axis=1) <= position[index])
        selected &= (triangles[:, :, index].max(axis=1) >= position[index])
    fixed = vector(position)
    hits = []
    for triangle in triangles[selected]:
        a, b, c = [vector(vertex) for vertex in triangle]
        normal = cross(subtract(b, a), subtract(c, a))
        area = dot(normal, normal)
        if area == 0:
            raise ValueError("扫描候选面退化")
        if normal[axis] == 0:
            if dot(normal, subtract(fixed, a)) == 0:
                raise ValueError("扫描线与候选面共面，不能判定区间")
            continue
        coordinate = a[axis] - sum(normal[index]*(fixed[index]-a[index]) for index in perpendicular) / normal[axis]
        point = list(fixed)
        point[axis] = coordinate
        weights = [dot(cross(subtract(b, point), subtract(c, point)), normal),
                   dot(cross(subtract(c, point), subtract(a, point)), normal),
                   dot(cross(subtract(a, point), subtract(b, point)), normal)]
        if min(weights) < 0:
            continue
        if min(weights) == 0:
            raise ValueError("扫描线命中三角边界，需另设独立探针")
        hits.append((coordinate, 1 if normal[axis] < 0 else -1))
    hits.sort()
    if len({coordinate for coordinate, _ in hits}) != len(hits):
        raise ValueError("同坐标存在多个交点，不能自动合并")
    intervals = []
    occupied = False
    start = None
    for coordinate, direction in hits:
        if direction == 1 and not occupied:
            start = coordinate
            occupied = True
        elif direction == -1 and occupied:
            intervals.append([float(start), float(coordinate)])
            occupied = False
        else:
            raise ValueError("扫描交点绕序或实体重叠异常")
    if occupied:
        raise ValueError("扫描线材料区间未闭合")
    return intervals


def compare_intervals(reference, candidate):
    """不同区间数单列，不强行把不同实体区间配对。"""
    result = {"reference_intervals_mm": reference, "candidate_intervals_mm": candidate,
              "interval_count_matches": len(reference) == len(candidate)}
    if reference and len(reference) == len(candidate):
        result["maximum_endpoint_difference_mm"] = float(np.max(np.abs(np.asarray(reference)-candidate)))
        result["maximum_material_width_difference_mm"] = float(np.max(np.abs(
            np.diff(np.asarray(reference), axis=1)-np.diff(np.asarray(candidate), axis=1))))
    else:
        result["maximum_endpoint_difference_mm"] = None
        result["maximum_material_width_difference_mm"] = None
    for label, intervals in (("reference", reference), ("candidate", candidate)):
        gaps = [second[0]-first[1] for first, second in zip(intervals, intervals[1:])
                if first[1] < 0 < second[0]]
        result[label+"_central_void_width_mm"] = gaps[0] if len(gaps) == 1 else None
    a, b = result["reference_central_void_width_mm"], result["candidate_central_void_width_mm"]
    result["central_void_presence_matches"] = (a is None) == (b is None)
    result["central_void_width_difference_mm"] = abs(a-b) if a is not None and b is not None else None
    return result
