"""跨精度坐标候选的局部材料单调性诊断；尚不提供全局无碰撞证书。"""

from fractions import Fraction
from itertools import product

import numpy as np
import trimesh
from scipy.optimize import Bounds, LinearConstraint, milp

from locality_retriangulate import invalid_faces


def exact_vector(values):
    """将已存储的二进制浮点值转换为精确有理数，不恢复CSG内部精确构造。"""
    return tuple(Fraction(float(value)) for value in values)


def subtract(a, b):
    return tuple(x - y for x, y in zip(a, b))


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def exact_star_guard(before, after, local_index, budget_origin, budget):
    """逐面检查向内法向速度及不翻转；全局嵌入性仍须独立连续碰撞检查。"""
    old_point = exact_vector(before[0, local_index[0]])
    new_point = exact_vector(after[0, local_index[0]])
    displacement = subtract(new_point, old_point)
    total = subtract(new_point, exact_vector(budget_origin))
    if dot(total, total) > Fraction(str(budget)) ** 2:
        return False
    for old_triangle, new_triangle in zip(before, after):
        old = [exact_vector(point) for point in old_triangle]
        new = [exact_vector(point) for point in new_triangle]
        normal = cross(subtract(old[1], old[0]), subtract(old[2], old[0]))
        new_normal = cross(subtract(new[1], new[0]), subtract(new[2], new[0]))
        if dot(normal, displacement) > 0 or dot(normal, new_normal) <= 0:
            return False
    return True


def integer_star_candidate(before, indices, nearest, spacing, budget, material_guard):
    """在预算内求整数网格可行点；浮点求解只提供候选，必须再经精确谓词审核。"""
    normals = np.cross(before[:, 1] - before[:, 0], before[:, 2] - before[:, 0])
    lengths = np.linalg.norm(normals, axis=1)
    if np.any(lengths == 0):
        return None
    normals /= lengths[:, None]
    current = before[0, indices[0]]
    rows, lower, upper = [], [], []
    for triangle, index, normal in zip(before, indices, normals):
        if material_guard:
            rows.append(np.r_[normal, [0., 0., 0.]])
            lower.append(-np.inf)
            # 留出求解器数值容差的向内裕量；最终仍以精确符号判定，不接受容差放宽。
            upper.append(float(normal @ (current - nearest) / spacing) - 1e-4)
        # FP32实际三角面的有向投影面积对单点坐标是线性的。
        rounded = triangle.astype(np.float32).astype(np.float64)
        rounded[index] = nearest
        def area(point):
            trial = rounded.copy()
            trial[index] = point
            return float(np.cross(trial[1] - trial[0], trial[2] - trial[0]) @ normal)
        base = area(nearest)
        coefficients = np.array([area(nearest + np.eye(3)[axis] * spacing) - base for axis in range(3)])
        scale = max(float(np.linalg.norm(coefficients)), 1e-300)
        rows.append(np.r_[coefficients / scale, [0., 0., 0.]])
        lower.append((2.1e-12 - base) / scale)
        upper.append(np.inf)
    # 辅助变量实现整数偏移的L1目标；最终位移仍按欧氏预算精确复核。
    for axis in range(3):
        for sign in (-1, 1):
            row = np.zeros(6)
            row[axis], row[axis + 3] = sign, -1
            rows.append(row)
            lower.append(-np.inf)
            upper.append(0.)
    radius = int(np.ceil(budget / spacing)) + 1
    result = milp(np.r_[np.zeros(3), np.ones(3)], integrality=np.r_[np.ones(3), np.zeros(3)],
                  bounds=Bounds(np.r_[np.full(3, -radius), np.zeros(3)], np.full(6, radius)),
                  constraints=LinearConstraint(np.array(rows), lower, upper), options={"time_limit": 1.0})
    if result.x is None:
        return None
    return (nearest + np.rint(result.x[:3]) * spacing).astype(np.float32).astype(np.float64)


def probe_repair(mesh, budget_mm=1e-5, material_guard=True):
    """仅诊断坏面顶点能否找到固定连接、有限位移的FP32坐标；不发布网格。"""
    vertices, faces = mesh.vertices.copy(), mesh.faces.copy()
    original = vertices.copy()
    initial = invalid_faces(vertices, faces)
    record = {"budget_mm": budget_mm, "material_guard": material_guard,
              "initial_invalid": int(initial.sum()), "moves": [],
              "scope": "开发诊断；局部法向约束不等于材料集合包含或全局无碰撞"}
    # 预算按初始坏面顶点集合冻结，不能根据结果不断扩展搜索。
    ids = np.unique(faces[initial])
    offsets = np.array(list(product((-2, -1, 0, 1, 2), repeat=3)))
    for vertex in ids:
        owners = np.flatnonzero(np.any(faces == vertex, axis=1))
        old_bad = invalid_faces(vertices, faces[owners])
        if not old_bad.any():
            continue
        indices = np.argmax(faces[owners] == vertex, axis=1)
        before = vertices[faces[owners]].copy()
        nearest = vertices[vertex].astype(np.float32)
        spacing = float(np.max(np.abs(np.spacing(nearest))))
        candidates = np.unique((nearest.astype(np.float64) + offsets * spacing)
                               .astype(np.float32).astype(np.float64), axis=0)
        candidates = sorted(candidates, key=lambda point: float(np.linalg.norm(point - original[vertex])))
        # 两组使用相同整数搜索预算；仅消融材料法向约束，避免混入搜索范围差异。
        solved = integer_star_candidate(before, indices, nearest.astype(np.float64), spacing, budget_mm, material_guard)
        if solved is not None:
            candidates.append(solved)
        winner = None
        winner_count = int(old_bad.sum())
        for point in candidates:
            if np.linalg.norm(point - original[vertex]) > budget_mm:
                continue
            after = before.copy()
            after[np.arange(len(owners)), indices] = point
            trial = vertices.copy()
            trial[vertex] = point
            new_bad = invalid_faces(trial, faces[owners])
            if np.any(new_bad & ~old_bad) or int(new_bad.sum()) >= winner_count:
                continue
            # 无约束对照只检验端点朝向；不能据此宣称全过程不相交。
            old_normals = np.cross(before[:, 1] - before[:, 0], before[:, 2] - before[:, 0])
            new_normals = np.cross(after[:, 1] - after[:, 0], after[:, 2] - after[:, 0])
            if np.any(np.sum(old_normals * new_normals, axis=1) <= 0):
                continue
            if material_guard and not exact_star_guard(before, after, indices, original[vertex], budget_mm):
                continue
            winner, winner_count = point, int(new_bad.sum())
            if winner_count == 0:
                break
        if winner is not None:
            vertices[vertex] = winner
            record["moves"].append({"vertex": int(vertex), "star_invalid_before": int(old_bad.sum()),
                                    "star_invalid_after": winner_count})
    record["remaining_invalid"] = int(invalid_faces(vertices, faces).sum())
    record["max_displacement_mm"] = float(np.max(np.linalg.norm(vertices - original, axis=1), initial=0))
    record["faces_exact"] = bool(np.array_equal(faces, mesh.faces))
    return trimesh.Trimesh(vertices, faces, process=False), record


def quantize_monotone(mesh, budget_mm=1e-5):
    """尝试完整FP32化；任一点不可行就拒绝，返回原件而非部分转换网格。"""
    original = mesh.vertices.copy()
    repaired, detail = probe_repair(mesh, budget_mm, material_guard=True)
    record = {"repair": detail, "budget_mm": budget_mm, "rounded_vertices": 0,
              "accepted": False, "scope": "精确局部法向符号和位移预算；未证明全局嵌入性"}
    if detail["remaining_invalid"]:
        record["reason"] = "unrepaired_degeneracy"
        return mesh.copy(), record
    vertices, faces = repaired.vertices.copy(), repaired.faces.copy()
    for vertex in range(len(vertices)):
        nearest = vertices[vertex].astype(np.float32).astype(np.float64)
        if np.array_equal(vertices[vertex], nearest):
            continue
        owners = np.flatnonzero(np.any(faces == vertex, axis=1))
        if not len(owners):
            record["reason"] = "unreferenced_vertex"
            return mesh.copy(), record
        indices = np.argmax(faces[owners] == vertex, axis=1)
        before = vertices[faces[owners]].copy()
        spacing = float(np.max(np.abs(np.spacing(nearest.astype(np.float32)))))
        candidates = [nearest]
        solved = integer_star_candidate(before, indices, nearest, spacing, budget_mm, True)
        if solved is not None:
            candidates.append(solved)
        selected = None
        for point in candidates:
            after = before.copy()
            after[np.arange(len(owners)), indices] = point
            if not exact_star_guard(before, after, indices, original[vertex], budget_mm):
                continue
            trial = vertices.copy()
            trial[vertex] = point
            if invalid_faces(trial, faces[owners]).any():
                continue
            selected = point
            break
        if selected is None:
            record.update(reason="no_verified_grid_candidate", failed_vertex=vertex)
            return mesh.copy(), record
        vertices[vertex] = selected
        record["rounded_vertices"] += 1
    record["accepted"] = True
    record["max_displacement_mm"] = float(np.max(np.linalg.norm(vertices - original, axis=1), initial=0))
    return trimesh.Trimesh(vertices, faces, process=False), record
