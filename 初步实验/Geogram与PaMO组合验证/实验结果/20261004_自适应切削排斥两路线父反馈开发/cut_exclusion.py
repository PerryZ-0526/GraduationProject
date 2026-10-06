"""用逐三角面支撑半空间约束，诊断和修复维护网格侵入凸切削工具的现象。"""

import numpy as np
import trimesh
from scipy.optimize import LinearConstraint, minimize
from fractions import Fraction


def dot_intervals(points, normals):
    """显式逐项外舍入，包围已存储二进制坐标的真实实数点积；不使用BLAS归约。"""
    lower = np.zeros((len(points), len(normals)))
    upper = lower.copy()
    for axis in range(3):
        product = points[:, axis, None] * normals[None, :, axis]
        lower = np.nextafter(lower + np.nextafter(product, -np.inf), -np.inf)
        upper = np.nextafter(upper + np.nextafter(product, np.inf), np.inf)
    return lower, upper


def supporting_planes(tool):
    """本版仅支持闭合凸工具，不能把累计非凸工具并集当作凸体。"""
    if not tool.is_convex or not tool.is_watertight or not tool.is_winding_consistent:
        raise ValueError("支撑约束需要闭合、朝向一致的凸工具")
    normals = tool.face_normals
    # 上界支撑偏置包围全部工具顶点，因此这些半空间的交集包含整个工具凸包。
    # 它是保守切削排斥域，不能把普通浮点面偏置误称为精确工具平面。
    offsets = np.full(len(normals), -np.inf)
    for start in range(0, len(tool.vertices), 256):
        _, upper = dot_intervals(tool.vertices[start:start + 256], normals)
        offsets = np.maximum(offsets, upper.max(axis=0))
    return normals, offsets


def certify_face_support(mesh, normals, offsets, selected):
    """用有理数精确核对每个顶点，给出整三角面排斥证据，不依赖顶点抽样推广。"""
    exact_normals = [tuple(Fraction(float(x)) for x in normal) for normal in normals]
    exact_offsets = [Fraction(float(value)) for value in offsets]
    failed = []
    for index, face in enumerate(mesh.faces):
        plane = int(selected[index])
        for point in mesh.vertices[face]:
            value = sum(coefficient * Fraction(float(coordinate))
                        for coefficient, coordinate in zip(exact_normals[plane], point)) - exact_offsets[plane]
            if value < 0:
                failed.append(index)
                break
    return {"passed": not failed, "failed_face_count": len(failed), "failed_face_ids": failed[:20],
            "certified_scope": "全部三角面避开外舍入支撑半空间交集的内部；不认证网格嵌入性或整体Hausdorff距离"}


def certify_outside_anchor(mesh, tool, normals, offsets):
    """寻找排斥域内部且位于骨面包围盒之外的点，排除整包工具的反例。"""
    center = tool.vertices.mean(axis=0)
    candidates = [center]
    for axis in range(3):
        for extreme in (np.argmin(tool.vertices[:, axis]), np.argmax(tool.vertices[:, axis])):
            candidates.append(.999 * tool.vertices[extreme] + .001 * center)
    low, high = mesh.bounds
    exact_normals = [tuple(Fraction(float(x)) for x in normal) for normal in normals]
    for point in candidates:
        if not np.any((point < low) | (point > high)):
            continue
        exact = tuple(Fraction(float(x)) for x in point)
        if all(sum(a * b for a, b in zip(normal, exact)) < Fraction(float(offset))
               for normal, offset in zip(exact_normals, offsets)):
            return {"passed": True, "point_mm": point.tolist(),
                    "scope": "点严格在支撑半空间交集内、骨面包围盒外；配合整面排斥和嵌入闭合前提才推出材料排斥"}
    return {"passed": False, "reason": "no_bounding_box_anchor", "scope": "未找到不等于材料相交，禁止以此放宽认证"}


def face_separators(mesh, tool):
    """为每个面选共同外半空间；顶点分别在外不能证明整个三角面在外。"""
    normals, offsets = supporting_planes(tool)
    selected = np.empty(len(mesh.faces), dtype=int)
    slack = np.empty(len(mesh.faces))
    for start in range(0, len(mesh.faces), 256):
        triangles = mesh.triangles[start:start + 256]
        signed = np.min(triangles @ normals.T - offsets, axis=1)
        indices = np.argmax(signed, axis=1)
        selected[start:start + len(indices)] = indices
        slack[start:start + len(indices)] = signed[np.arange(len(indices)), indices]
    return selected, slack


def repair_cut_exclusion(mesh, tool, budget_mm=.1, clearance_mm=1e-8):
    """冻结逐面支撑后求逐点最小位移；不能替代全局碰撞、拓扑或距离审计。"""
    return repair_cut_exclusion_many(mesh, [tool], budget_mm, clearance_mm)


def repair_cut_exclusion_many(mesh, tools, budget_mm=.1, clearance_mm=1e-8, target_vertices=None):
    """所有累计凸工具共同进入同一次投影，防止修复新刀时重新侵入旧刀区域。"""
    if target_vertices is None:
        targets = mesh.vertices.copy()
    else:
        targets = np.asarray(target_vertices, dtype=np.float64)
        if targets.shape != mesh.vertices.shape or not np.isfinite(targets).all():
            raise ValueError("独立累计参照的目标坐标尺寸或有限性无效")
    assignment_mesh = trimesh.Trimesh(targets, mesh.faces.copy(), process=False)
    normal_blocks, offset_blocks, selections, slacks = [], [], [], []
    shift = 0
    for tool in tools:
        normals, offsets = supporting_planes(tool)
        selected, before = face_separators(assignment_mesh, tool)
        normal_blocks.append(normals)
        offset_blocks.append(offsets)
        selections.append(selected + shift)
        slacks.append(before)
        shift += len(normals)
    normals, offsets = np.concatenate(normal_blocks), np.concatenate(offset_blocks)
    selected, before = np.array(selections), np.array(slacks)
    vertices = targets.copy()
    record = {"budget_mm": budget_mm, "clearance_mm": clearance_mm,
              "initial_uncertified_faces": int(np.sum(before < -1e-9)),
              "cumulative_tools": len(tools),
              "objective_target": "raw_maintained_vertices" if target_vertices is None else "independent_cumulative_reference_closest_points",
              "frozen_face_support_ids": selected.tolist(),
              "moved_vertices": 0, "accepted": False,
              "scope": "浮点半空间候选；材料集合及连续几何证书需要独立认证"}
    # 面支撑分配在移动前冻结，禁止边修边换支撑来掩盖约束违反。
    for vertex in range(len(vertices)):
        owners = np.flatnonzero(np.any(mesh.faces == vertex, axis=1))
        planes = np.unique(selected[:, owners])
        matrix, right = normals[planes], offsets[planes] + clearance_mm
        origin = vertices[vertex].copy()
        origin_inside_budget = np.linalg.norm(origin - mesh.vertices[vertex]) <= budget_mm
        if np.all(matrix @ origin >= right) and origin_inside_budget:
            continue
        # 平移为小尺度位移变量，避免大世界坐标下目标函数精度损失。
        bounds = right - matrix @ origin
        constraints = [LinearConstraint(matrix, bounds, np.inf)]
        if target_vertices is not None:
            # 参照最近点可在信赖球之外，必须求有界凸投影，不能先无界投影再一律拒绝。
            center = mesh.vertices[vertex] - origin
            radius = budget_mm - 1e-10
            constraints.append({"type": "ineq", "fun": lambda delta: radius ** 2 - float((delta - center) @ (delta - center)),
                                "jac": lambda delta: -2 * (delta - center)})
        result = minimize(lambda delta: .5 * float(delta @ delta), np.zeros(3),
                          jac=lambda delta: delta, method="SLSQP",
                          constraints=constraints,
                          options={"ftol": 1e-15, "maxiter": 50})
        if not result.success or np.max(bounds - matrix @ result.x, initial=0) > 1e-10:
            record.update(reason="infeasible_or_unverified_projection", failed_vertex=vertex)
            return mesh.copy(), record
        if np.linalg.norm(origin + result.x - mesh.vertices[vertex]) > budget_mm:
            record.update(reason="displacement_budget_exceeded", failed_vertex=vertex)
            return mesh.copy(), record
        vertices[vertex] = origin + result.x
        record["moved_vertices"] += 1
    candidate = trimesh.Trimesh(vertices, mesh.faces.copy(), process=False)
    # 相同连接给出逐顶点对应关系，精确位移预算可推广为两张表面的双向距离上界。
    bound = Fraction(str(budget_mm)) ** 2
    displacement_passed = all(sum((Fraction(float(a)) - Fraction(float(b))) ** 2 for a, b in zip(point, old)) <= bound
                              for point, old in zip(vertices, mesh.vertices))
    if not displacement_passed:
        record.update(reason="exact_correspondence_displacement_budget_exceeded")
        return mesh.copy(), record
    # 按原冻结支撑复核，而不是用重新分配的支撑证明本次位移满足约束。
    values = np.array([np.min(np.sum(candidate.triangles * normals[choice, None, :], axis=2)
                             - offsets[choice, None], axis=1) for choice in selected])
    certificates = [certify_face_support(candidate, normals, offsets, choice) for choice in selected]
    anchors = [certify_outside_anchor(candidate, tool, n, b)
               for tool, n, b in zip(tools, normal_blocks, offset_blocks)]
    record.update(remaining_uncertified_faces=int(np.sum(values < -1e-9)),
                  max_displacement_mm=float(np.linalg.norm(vertices - mesh.vertices, axis=1).max(initial=0)),
                  faces_exact=bool(np.array_equal(candidate.faces, mesh.faces)),
                  correction_correspondence_bound={"passed": True, "upper_bound_mm": budget_mm,
                                                   "scope": "相对本次原版维护输出的同连接表面，不是相对累计真实目标的证书"},
                  face_support_certificate=certificates[0] if len(tools) == 1 else certificates,
                  outside_anchor_certificate=anchors[0] if len(tools) == 1 else anchors,
                  accepted=all(c["passed"] for c in certificates) and all(a["passed"] for a in anchors))
    return (candidate if record["accepted"] else mesh.copy()), record
