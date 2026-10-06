"""用输入浮点数的精确有理数表示，证明报警面对分离或仅共享单纯形。"""

from fractions import Fraction
import numpy as np
from scipy.optimize import linprog


def sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


def dot(a, b):
    return sum(x*y for x, y in zip(a, b))


def prove_contact(vertices, first, second):
    """只接受严格分离，或分离支撑面两侧都恰为共同索引顶点的情形。"""
    shared = set(map(int, first)) & set(map(int, second))
    if len(shared) == 3:
        return {"proved": False, "kind": "duplicate_triangle_unresolved"}
    points = {int(i): tuple(Fraction(float(x)) for x in vertices[i])
              for i in set(map(int, first)) | set(map(int, second))}
    a, b = [points[int(i)] for i in first], [points[int(i)] for i in second]
    ea = [sub(a[(i+1)%3], a[i]) for i in range(3)]
    eb = [sub(b[(i+1)%3], b[i]) for i in range(3)]
    na, nb = cross(ea[0], ea[1]), cross(eb[0], eb[1])
    axes = [na, nb] + [cross(x, y) for x in ea for y in eb]
    axes += [cross(na, x) for x in ea] + [cross(nb, x) for x in eb]
    for axis in axes:
        if not any(axis):
            continue
        pa, pb = [dot(x, axis) for x in a], [dot(x, axis) for x in b]
        for left, right, li, ri in ((pa, pb, first, second), (pb, pa, second, first)):
            hi, lo = max(left), min(right)
            if hi < lo:
                return {"proved": True, "kind": "strict_separation"}
            if hi == lo and shared:
                support_left = {int(i) for i, x in zip(li, left) if x == hi}
                support_right = {int(i) for i, x in zip(ri, right) if x == lo}
                if support_left == support_right == shared:
                    return {"proved": True, "kind": "shared_simplex_only", "shared_vertices": sorted(shared)}
    # 数值规划仅寻找候选轴；最终仍以有理数严格验证，不以求解器容差接受。
    if 0 < len(shared) < 3:
        origin = points[min(shared)]
        other_a = [sub(points[int(i)], origin) for i in first if int(i) not in shared]
        other_b = [sub(points[int(i)], origin) for i in second if int(i) not in shared]
        inequalities = np.array([list(map(float, x)) for x in other_a] +
                                 [[-float(t) for t in x] for x in other_b])
        lengths = np.linalg.norm(inequalities, axis=1)
        if np.all(lengths > 0):
            edge = sub(points[max(shared)], origin) if len(shared) == 2 else None
            solved = linprog(np.zeros(3), A_ub=inequalities / lengths[:, None],
                b_ub=-np.ones(len(inequalities)),
                A_eq=np.array([list(map(float, edge))]) if edge is not None else None,
                b_eq=np.zeros(1) if edge is not None else None,
                bounds=[(None, None)] * 3, method="highs")
            if solved.success:
                axis = tuple(Fraction(float(x)) for x in solved.x)
                if edge is not None:
                    axis = sub(axis, tuple(x * dot(axis, edge) / dot(edge, edge) for x in edge))
                if all(dot(x, axis) < 0 for x in other_a) and all(dot(x, axis) > 0 for x in other_b):
                    return {"proved": True, "kind": "shared_simplex_only", "shared_vertices": sorted(shared)}
    return {"proved": False, "kind": "unresolved"}


def mesh_valid_exact_contacts(mesh):
    """保留旧数值门槛，只补强原报警集合内的共享接触证明。"""
    import pymeshlab as pm
    from geometry_preservation_audit import mesh_valid, triangle_separation_gap
    valid, metrics = mesh_valid(mesh)
    if not (0 < metrics["self_intersection_faces"] <= 200):
        return valid, metrics
    detector = pm.MeshSet()
    detector.add_mesh(pm.Mesh(np.asarray(mesh.vertices), np.asarray(mesh.faces)))
    detector.compute_selection_by_self_intersections_per_face()
    ids = np.flatnonzero(detector.current_mesh().face_selection_array())
    unresolved, proofs = set(), []
    for n, first in enumerate(ids):
        for second in ids[n+1:]:
            if triangle_separation_gap(mesh.triangles[first], mesh.triangles[second]) > 1e-9:
                continue
            proof = prove_contact(mesh.vertices, mesh.faces[first], mesh.faces[second])
            proofs.append(dict(faces=[int(first), int(second)], **proof))
            if not proof["proved"]:
                unresolved.update((int(first), int(second)))
    metrics["historical_unresolved_alarm_faces"] = metrics["self_intersection_faces"]
    metrics["exact_alarm_pair_proofs"] = proofs
    metrics["self_intersection_faces"] = len(unresolved)
    metrics["intersection_check_interpretation"] = "原报警集合内精确有理数分离及共享接触证明；非完整自交证书"
    valid = all((metrics["finite"], metrics["zero_area_faces"] == 0, metrics["watertight"],
                 metrics["winding_consistent"], metrics["vertex_manifold_closed"], not unresolved))
    return valid, metrics
