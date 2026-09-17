"""基于解析材料集合的计划完成度、剩余量和越界体积。"""
import numpy as np
from numpy.polynomial.legendre import leggauss

from surface_methods import plane_height, top_connected_height


def _disk_quadrature(center, radius, order):
    nodes, weights = leggauss(order)
    radial = radius * (nodes + 1.0) / 2.0
    radial_weights = radius * weights / 2.0
    angles = np.pi * (nodes + 1.0)
    angular_weights = np.pi * weights
    rr, theta = np.meshgrid(radial, angles, indexing="ij")
    xy = np.column_stack(
        (
            center[0] + (rr * np.cos(theta)).reshape(-1),
            center[1] + (rr * np.sin(theta)).reshape(-1),
        )
    )
    area_weights = (
        radial_weights[:, None]
        * angular_weights[None, :]
        * rr
    ).reshape(-1)
    return xy, area_weights


def _rectangle_quadrature(bounds, order):
    nodes, weights = leggauss(order)
    x_low, x_high, y_low, y_high = map(float, bounds)
    x = x_low + (x_high - x_low) * (nodes + 1.0) / 2.0
    y = y_low + (y_high - y_low) * (nodes + 1.0) / 2.0
    x_weights = (x_high - x_low) * weights / 2.0
    y_weights = (y_high - y_low) * weights / 2.0
    xy = np.stack(np.meshgrid(x, y, indexing="ij"), axis=-1).reshape(-1, 2)
    area_weights = (
        x_weights[:, None] * y_weights[None, :]
    ).reshape(-1)
    return xy, area_weights


def _removed_depth(xy, case, replay):
    initial = plane_height(xy, case)
    current, _, diagnostics = top_connected_height(xy, case, replay)
    if not diagnostics["all_removed_intervals_top_connected"]:
        raise ValueError("状态体积只适用于全部去除区间与外表面连通的案例")
    return np.maximum(initial - current, 0.0)


def planned_state_metrics(case, replay, quadrature_order=256):
    """计算不会因重复路径重复累计的计划体积状态。"""
    target_depth = case.get("plan", {}).get("target_depth_mm")
    if not isinstance(target_depth, (int, float)) or target_depth <= 0:
        raise ValueError("状态答案需要plan.target_depth_mm为正数")
    if not isinstance(quadrature_order, int) or quadrature_order < 16:
        raise ValueError("quadrature_order必须是不小于16的整数")

    center = np.asarray(case["plan"]["center_xy_mm"], dtype=np.float64)
    radius = float(case["plan"]["allowed_radius_mm"])
    inside_xy, inside_weights = _disk_quadrature(
        center,
        radius,
        quadrature_order,
    )
    inside_actual_depth = _removed_depth(inside_xy, case, replay)
    achieved_depth = np.minimum(inside_actual_depth, target_depth)
    overcut_depth = np.maximum(inside_actual_depth - target_depth, 0.0)

    starts = np.asarray(
        [primitive["start"][:2] for primitive in replay["primitives"]],
        dtype=np.float64,
    )
    ends = np.asarray(
        [primitive["end"][:2] for primitive in replay["primitives"]],
        dtype=np.float64,
    )
    radii = np.asarray(
        [primitive["radius"] for primitive in replay["primitives"]],
        dtype=np.float64,
    )
    if len(radii):
        all_centers = np.vstack((starts, ends))
        expanded_radii = np.concatenate((radii, radii))
        bounds = (
            np.min(all_centers[:, 0] - expanded_radii),
            np.max(all_centers[:, 0] + expanded_radii),
            np.min(all_centers[:, 1] - expanded_radii),
            np.max(all_centers[:, 1] + expanded_radii),
        )
        total_xy, total_weights = _rectangle_quadrature(
            bounds,
            quadrature_order,
        )
        independently_integrated_total = float(
            np.sum(_removed_depth(total_xy, case, replay) * total_weights)
        )
    else:
        bounds = (center[0], center[0], center[1], center[1])
        independently_integrated_total = 0.0

    planned_volume = float(np.pi * radius**2 * target_depth)
    inside_actual_volume = float(
        np.sum(inside_actual_depth * inside_weights)
    )
    achieved_volume = float(np.sum(achieved_depth * inside_weights))
    remaining_volume = planned_volume - achieved_volume
    overcut_volume = float(np.sum(overcut_depth * inside_weights))
    corners = np.asarray(
        [
            [bounds[0], bounds[2]],
            [bounds[0], bounds[3]],
            [bounds[1], bounds[2]],
            [bounds[1], bounds[3]],
        ]
    )
    swept_bounds_inside_plan = bool(
        np.all(np.linalg.norm(corners - center, axis=1) <= radius)
    )
    outside_plan_volume = (
        0.0
        if swept_bounds_inside_plan
        else max(independently_integrated_total - inside_actual_volume, 0.0)
    )
    total_actual_volume = inside_actual_volume + outside_plan_volume
    completion = min(max(achieved_volume / planned_volume, 0.0), 1.0)
    return {
        "planned_removal_volume_mm3": planned_volume,
        "achieved_within_plan_volume_mm3": achieved_volume,
        "remaining_within_plan_volume_mm3": remaining_volume,
        "overcut_within_plan_volume_mm3": overcut_volume,
        "outside_plan_removed_volume_mm3": outside_plan_volume,
        "completion_fraction": completion,
        "actual_removed_volume_mm3": total_actual_volume,
        "inside_plan_actual_removed_volume_mm3": inside_actual_volume,
        "independently_integrated_total_removed_volume_mm3": (
            independently_integrated_total
        ),
        "integration_closure_residual_mm3": (
            independently_integrated_total - total_actual_volume
        ),
        "swept_bounds_inside_plan": swept_bounds_inside_plan,
        "target_depth_mm": float(target_depth),
        "quadrature_order": quadrature_order,
        "integration_bounds_xy_mm": list(map(float, bounds)),
        "scope": (
            "解析平面、顶部连通单值去除和圆形计划域上的确定性体积；"
            "数值为高阶Gauss-Legendre求积，不是实测骨量"
        ),
    }
