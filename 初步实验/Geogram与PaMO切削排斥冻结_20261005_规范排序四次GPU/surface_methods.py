"""倾斜单值表面的解析候选与普通体素等值面工程基线。"""
from functools import lru_cache
from time import perf_counter

import numpy as np
import pyvista as pv

from motion_record import actual_material_field


QUALITY_MIN_ANGLE_DEG = 25.0
QUALITY_MIN_Q = 0.4
SOURCE_SNAP_FRACTION = 0.35
TRANSITION_CONTINUITY_TOLERANCE_MM = 1e-8
CONSTRAINT_SEARCH_SAMPLES = 33
CONSTRAINT_SEARCH_LEVELS = 3
CONSTRAINT_OPTIMIZATION_SWEEPS = 3


def plane_height(xy, case):
    """返回初始解析平面在水平坐标处的高度。"""
    xy = np.asarray(xy, dtype=np.float64)
    a, b, offset = case["initial_surface"]["height_coefficients"]
    return a * xy[..., 0] + b * xy[..., 1] + offset


def capsule_vertical_interval(xy, primitive, tolerance=1e-12):
    """精确求固定水平位置与任意三维胶囊相交的最低和最高z。"""
    xy = np.asarray(xy, dtype=np.float64)
    if xy.shape[-1] != 2:
        raise ValueError("xy末维必须为2")
    original_shape = xy.shape[:-1]
    flat = xy.reshape(-1, 2)
    start = np.asarray(primitive["start"], dtype=np.float64)
    end = np.asarray(primitive["end"], dtype=np.float64)
    delta = end - start
    radius = float(primitive["radius"])

    lower = np.full(len(flat), np.inf, dtype=np.float64)
    upper = np.full(len(flat), -np.inf, dtype=np.float64)

    def include(values, valid):
        nonlocal lower, upper
        lower = np.where(valid, np.minimum(lower, values), lower)
        upper = np.where(valid, np.maximum(upper, values), upper)

    # A finite capsule is the union of its two endpoint spheres and the
    # axis-projected part of the corresponding infinite cylinder.
    for center in (start, end):
        radicand = radius**2 - np.sum((flat - center[:2]) ** 2, axis=1)
        valid = radicand >= -tolerance
        root = np.sqrt(np.maximum(radicand, 0.0))
        include(center[2] - root, valid)
        include(center[2] + root, valid)

    squared_length = float(delta @ delta)
    horizontal_squared = float(delta[:2] @ delta[:2])
    if squared_length > tolerance**2 and horizontal_squared > tolerance**2:
        relative_xy = flat - start[:2]
        projected_xy = relative_xy @ delta[:2]
        coefficient_a = horizontal_squared / squared_length
        coefficient_b = -2.0 * projected_xy * delta[2] / squared_length
        coefficient_c = (
            np.sum(relative_xy**2, axis=1)
            - projected_xy**2 / squared_length
            - radius**2
        )
        discriminant = coefficient_b**2 - 4.0 * coefficient_a * coefficient_c
        intersects = discriminant >= -tolerance
        root = np.sqrt(np.maximum(discriminant, 0.0))
        for relative_z in (
            (-coefficient_b - root) / (2.0 * coefficient_a),
            (-coefficient_b + root) / (2.0 * coefficient_a),
        ):
            axis_parameter = (
                projected_xy + relative_z * delta[2]
            ) / squared_length
            valid = (
                intersects
                & (axis_parameter >= -tolerance)
                & (axis_parameter <= 1.0 + tolerance)
            )
            include(start[2] + relative_z, valid)

    missed = ~np.isfinite(lower)
    lower[missed] = np.nan
    upper[missed] = np.nan
    return lower.reshape(original_shape), upper.reshape(original_shape)


def top_connected_height(xy, case, replay, tolerance=1e-12):
    """求与初始外表面连通的切削下包络，并报告被遮住的内部空腔。"""
    xy = np.asarray(xy, dtype=np.float64)
    original_shape = xy.shape[:-1]
    flat = xy.reshape(-1, 2)
    initial = plane_height(flat, case)
    height = initial.copy()
    source = np.full(len(flat), -1, dtype=np.int32)
    intervals = [
        capsule_vertical_interval(flat, primitive)
        for primitive in replay["primitives"]
    ]

    iterations = 0
    for _ in range(len(intervals) + 1):
        iterations += 1
        if not intervals:
            break
        connected_lows = np.stack(
            [
                np.where(
                    np.isfinite(lower) & (upper >= height - tolerance),
                    lower,
                    np.inf,
                )
                for lower, upper in intervals
            ],
            axis=0,
        )
        primitive_index = np.argmin(connected_lows, axis=0)
        lowest = np.min(connected_lows, axis=0)
        lowered = lowest < height - tolerance
        if not np.any(lowered):
            break
        height[lowered] = lowest[lowered]
        source[lowered] = primitive_index[lowered]

    cavity = np.zeros(len(flat), dtype=bool)
    for lower, upper in intervals:
        cavity |= (
            np.isfinite(lower)
            & (lower < initial - tolerance)
            & (upper < height - tolerance)
        )
    diagnostics = {
        "sample_count": len(flat),
        "cut_sample_count": int(np.count_nonzero(height < initial - tolerance)),
        "internal_cavity_sample_count": int(np.count_nonzero(cavity)),
        "all_removed_intervals_top_connected": not np.any(cavity),
        "connection_iterations": iterations,
    }
    return (
        height.reshape(original_shape),
        source.reshape(original_shape),
        diagnostics,
    )


def _axis(bounds, spacing):
    low, high = map(float, bounds)
    count = int(round((high - low) / spacing))
    if count <= 0 or abs(low + count * spacing - high) > 1e-10:
        raise ValueError("边界宽度必须是spacing的整数倍")
    return np.linspace(low, high, count + 1)


def _triangle_minimum_angles(points, faces):
    triangles = points[faces]
    angles = []
    for vertex in range(3):
        left = triangles[..., (vertex + 1) % 3, :] - triangles[..., vertex, :]
        right = triangles[..., (vertex + 2) % 3, :] - triangles[..., vertex, :]
        norm = np.linalg.norm(left, axis=-1) * np.linalg.norm(right, axis=-1)
        cosine = np.divide(
            np.sum(left * right, axis=-1),
            norm,
            out=np.ones_like(norm),
            where=norm > 0,
        )
        angles.append(np.degrees(np.arccos(np.clip(cosine, -1.0, 1.0))))
    return np.min(np.stack(angles, axis=-1), axis=-1)


def _triangle_quality_values(points, faces):
    triangles = np.asarray(points, dtype=np.float64)[faces]
    edges = triangles - np.roll(triangles, 1, axis=1)
    lengths = np.linalg.norm(edges, axis=2)
    areas = (
        np.linalg.norm(
            np.cross(
                triangles[:, 1] - triangles[:, 0],
                triangles[:, 2] - triangles[:, 0],
            ),
            axis=1,
        )
        / 2.0
    )
    denominator = np.sum(lengths**2, axis=1)
    quality = np.divide(
        4.0 * np.sqrt(3.0) * areas,
        denominator,
        out=np.zeros_like(areas),
        where=denominator > 0,
    )
    return quality, _triangle_minimum_angles(points, faces), areas


def _structured_cell_faces(xy, points, case, replay):
    nx, ny = xy.shape[:2]
    cell_i, cell_j = np.meshgrid(
        np.arange(nx - 1),
        np.arange(ny - 1),
        indexing="ij",
    )
    lower_left = (cell_i * ny + cell_j).reshape(-1)
    lower_right = ((cell_i + 1) * ny + cell_j).reshape(-1)
    upper_right = ((cell_i + 1) * ny + cell_j + 1).reshape(-1)
    upper_left = (cell_i * ny + cell_j + 1).reshape(-1)
    diagonal_lower_left = np.stack(
        (
            np.stack((lower_left, lower_right, upper_right), axis=1),
            np.stack((lower_left, upper_right, upper_left), axis=1),
        ),
        axis=1,
    )
    diagonal_lower_right = np.stack(
        (
            np.stack((lower_left, lower_right, upper_left), axis=1),
            np.stack((lower_right, upper_right, upper_left), axis=1),
        ),
        axis=1,
    )
    first_angle = np.min(
        _triangle_minimum_angles(points, diagonal_lower_left),
        axis=1,
    )
    second_angle = np.min(
        _triangle_minimum_angles(points, diagonal_lower_right),
        axis=1,
    )

    center_xy = (
        xy[:-1, :-1]
        + xy[1:, :-1]
        + xy[1:, 1:]
        + xy[:-1, 1:]
    ) / 4.0
    center_height, _, center_diagnostics = top_connected_height(
        center_xy,
        case,
        replay,
    )
    first_error = np.abs(
        (points[lower_left, 2] + points[upper_right, 2]) / 2.0
        - center_height.reshape(-1)
    )
    second_error = np.abs(
        (points[lower_right, 2] + points[upper_left, 2]) / 2.0
        - center_height.reshape(-1)
    )
    first_passes = first_angle >= QUALITY_MIN_ANGLE_DEG
    second_passes = second_angle >= QUALITY_MIN_ANGLE_DEG
    use_first = np.where(
        first_passes & second_passes,
        first_error <= second_error,
        np.where(
            first_passes,
            True,
            np.where(second_passes, False, first_angle >= second_angle),
        ),
    )
    faces = np.where(
        use_first[:, None, None],
        diagonal_lower_left,
        diagonal_lower_right,
    )
    corners = np.stack(
        (lower_left, lower_right, upper_right, upper_left),
        axis=1,
    )
    return faces, corners, use_first, center_diagnostics


def height_surface(case, replay, xy_bounds, spacing):
    """在固定XY网格上生成解析下包络候选。"""
    x = _axis(xy_bounds[:2], spacing)
    y = _axis(xy_bounds[2:], spacing)
    xy = np.stack(np.meshgrid(x, y, indexing="ij"), axis=-1)
    height, sources, diagnostics = top_connected_height(xy, case, replay)
    points = np.column_stack((xy.reshape(-1, 2), height.reshape(-1)))
    cell_faces, _, use_first, center_diagnostics = _structured_cell_faces(
        xy,
        points,
        case,
        replay,
    )
    faces = cell_faces.reshape(-1, 3)
    mesh = pv.PolyData(
        points,
        np.column_stack((np.full(len(faces), 3, dtype=np.int64), faces)),
    )
    mesh.point_data["source_index"] = sources.reshape(-1)
    diagnostics.update(
        {
            "grid_dimensions_xy": [len(x), len(y)],
            "spacing_mm": float(spacing),
            "cell_center_sample_count": center_diagnostics["sample_count"],
            "cell_center_internal_cavity_sample_count": center_diagnostics[
                "internal_cavity_sample_count"
            ],
            "all_removed_intervals_top_connected": (
                diagnostics["all_removed_intervals_top_connected"]
                and center_diagnostics["all_removed_intervals_top_connected"]
            ),
            "diagonal_policy": (
                "先满足最小角门槛，再选择单元中心解析高度误差较小的对角线"
            ),
            "first_diagonal_cells": int(np.count_nonzero(use_first)),
            "second_diagonal_cells": int(np.count_nonzero(~use_first)),
        }
    )
    return mesh, diagnostics


def _source_transitions(starts, ends, start_sources, case, replay):
    """批量二分来源切换，并返回切换两侧高度差。"""
    low = np.asarray(starts, dtype=np.float64).copy()
    high = np.asarray(ends, dtype=np.float64).copy()
    start_sources = np.asarray(start_sources, dtype=np.int32)
    for _ in range(50):
        middle = (low + high) / 2.0
        _, middle_source, _ = top_connected_height(
            middle,
            case,
            replay,
        )
        same = middle_source == start_sources
        low = np.where(same[:, None], middle, low)
        high = np.where(same[:, None], high, middle)
    low_height, _, _ = top_connected_height(low, case, replay)
    high_height, _, _ = top_connected_height(high, case, replay)
    return (low + high) / 2.0, np.abs(low_height - high_height)


def _source_transition(start, end, start_source, case, replay):
    roots, jumps = _source_transitions(
        np.asarray(start, dtype=np.float64)[None, :],
        np.asarray(end, dtype=np.float64)[None, :],
        np.asarray([start_source], dtype=np.int32),
        case,
        replay,
    )
    return roots[0], float(jumps[0])


def _scan_grid_source_transitions(xy, case, replay):
    """按0.25格距扫描整张规则网格，区分连续交线与高度跳变。"""
    horizontal_start = xy[:-1, :, :].reshape(-1, 2)
    horizontal_end = xy[1:, :, :].reshape(-1, 2)
    vertical_start = xy[:, :-1, :].reshape(-1, 2)
    vertical_end = xy[:, 1:, :].reshape(-1, 2)
    starts = np.vstack((horizontal_start, vertical_start))
    ends = np.vstack((horizontal_end, vertical_end))
    fractions = np.linspace(0.0, 1.0, 5)
    samples = (
        starts[:, None, :]
        + fractions[None, :, None] * (ends - starts)[:, None, :]
    )
    _, labels, _ = top_connected_height(samples, case, replay)
    changes = labels[:, :-1] != labels[:, 1:]
    if not np.any(changes):
        jumps = np.empty(0, dtype=np.float64)
    else:
        bracket_starts = samples[:, :-1, :][changes]
        bracket_ends = samples[:, 1:, :][changes]
        start_sources = labels[:, :-1][changes]
        _, jumps = _source_transitions(
            bracket_starts,
            bracket_ends,
            start_sources,
            case,
            replay,
        )
    discontinuous = jumps > TRANSITION_CONTINUITY_TOLERANCE_MM
    return {
        "global_source_transition_count": int(len(jumps)),
        "global_source_transition_scan_fraction": 0.25,
        "global_source_transition_max_one_sided_jump_mm": float(
            np.max(jumps, initial=0.0)
        ),
        "global_discontinuous_source_transition_count": int(
            np.count_nonzero(discontinuous)
        ),
        "global_source_transition_continuous": not np.any(discontinuous),
    }


def _fit_source_transitions(
    xy,
    sources,
    case,
    replay,
    spacing,
    movable_vertices,
    inspected_edges,
):
    """将邻近格点移到连续来源切换线上，并保留防翻转余量。"""
    fitted = np.asarray(xy, dtype=np.float64).copy()
    proposals = {}
    transition_count = 0
    transition_jumps = []

    def inspect_edge(first, second):
        nonlocal transition_count
        start = xy[first]
        end = xy[second]
        fractions = np.linspace(0.0, 1.0, 5)
        samples = start + fractions[:, None] * (end - start)
        _, labels, _ = top_connected_height(samples, case, replay)
        for sample_index in range(len(samples) - 1):
            if labels[sample_index] == labels[sample_index + 1]:
                continue
            root, jump = _source_transition(
                samples[sample_index],
                samples[sample_index + 1],
                labels[sample_index],
                case,
                replay,
            )
            transition_count += 1
            transition_jumps.append(jump)
            if jump > TRANSITION_CONTINUITY_TOLERANCE_MM:
                continue
            for vertex in (first, second):
                if vertex not in movable_vertices:
                    continue
                if (
                    vertex[0] in {0, sources.shape[0] - 1}
                    or vertex[1] in {0, sources.shape[1] - 1}
                ):
                    continue
                distance = float(np.linalg.norm(root - xy[vertex]))
                if distance > SOURCE_SNAP_FRACTION * spacing:
                    continue
                previous = proposals.get(vertex)
                if previous is None or distance < previous[0]:
                    proposals[vertex] = (distance, root)

    for first, second in sorted(inspected_edges):
        inspect_edge(first, second)

    for vertex, (_, root) in proposals.items():
        fitted[vertex] = root
    return fitted, {
        "source_transition_count": transition_count,
        "source_transition_edges_inspected": len(inspected_edges),
        "source_transition_scan_scope": (
            "仅检查原始候选质量失败单元的边；通过单元不移动"
        ),
        "source_transition_max_one_sided_jump_mm": float(
            max(transition_jumps, default=0.0)
        ),
        "source_transition_continuous": (
            max(transition_jumps, default=0.0)
            <= TRANSITION_CONTINUITY_TOLERANCE_MM
        ),
        "source_transition_continuity_tolerance_mm": (
            TRANSITION_CONTINUITY_TOLERANCE_MM
        ),
        "snapped_vertex_count": len(proposals),
        "maximum_snap_distance_mm": float(
            max((item[0] for item in proposals.values()), default=0.0)
        ),
        "snap_fraction_of_spacing": SOURCE_SNAP_FRACTION,
    }


def _normalized_triangle_quality(points, face):
    quality, angle, area = _triangle_quality_values(
        np.asarray(points, dtype=np.float64),
        np.asarray([face], dtype=np.int64),
    )
    if area[0] <= 1e-12:
        return 0.0
    return float(
        min(
            quality[0] / QUALITY_MIN_Q,
            angle[0] / QUALITY_MIN_ANGLE_DEG,
        )
    )


def _best_polygon_triangulation(polygon, points):
    """对小型凸单元选择最大化最差三维质量的无交叉三角剖分。"""
    polygon = tuple(map(int, polygon))

    @lru_cache(maxsize=None)
    def solve(first, last):
        if last <= first + 1:
            return np.inf, ()
        best_score = -np.inf
        best_faces = ()
        for middle in range(first + 1, last):
            left_score, left_faces = solve(first, middle)
            right_score, right_faces = solve(middle, last)
            face = (
                polygon[first],
                polygon[middle],
                polygon[last],
            )
            score = min(
                left_score,
                right_score,
                _normalized_triangle_quality(points, face),
            )
            if score > best_score:
                best_score = score
                best_faces = left_faces + right_faces + (face,)
        return best_score, best_faces

    return solve(0, len(polygon) - 1)


def source_fitted_height_surface(case, replay, xy_bounds, spacing):
    """对齐连续来源切换线，并只细分未通过质量门槛的局部单元。"""
    x = _axis(xy_bounds[:2], spacing)
    y = _axis(xy_bounds[2:], spacing)
    regular_xy = np.stack(np.meshgrid(x, y, indexing="ij"), axis=-1)
    regular_height, regular_sources, diagnostics = top_connected_height(
        regular_xy,
        case,
        replay,
    )
    regular_points = np.column_stack(
        (regular_xy.reshape(-1, 2), regular_height.reshape(-1))
    )
    regular_cell_faces, regular_corners, _, _ = _structured_cell_faces(
        regular_xy,
        regular_points,
        case,
        replay,
    )
    regular_quality, regular_angles, regular_areas = _triangle_quality_values(
        regular_points,
        regular_cell_faces.reshape(-1, 3),
    )
    regular_bad_faces = (
        ~np.isfinite(regular_quality)
        | ~np.isfinite(regular_angles)
        | (regular_quality < QUALITY_MIN_Q)
        | (regular_angles < QUALITY_MIN_ANGLE_DEG)
        | (regular_areas <= 1e-12)
    )
    regular_bad_cells = np.any(regular_bad_faces.reshape(-1, 2), axis=1)
    movable_vertices = {
        np.unravel_index(
            int(vertex),
            regular_sources.shape,
        )
        for vertex in regular_corners[regular_bad_cells].reshape(-1)
    }
    inspected_edges = set()
    for cell_corners in regular_corners[regular_bad_cells]:
        for first, second in zip(
            cell_corners,
            np.roll(cell_corners, -1),
        ):
            first_vertex = np.unravel_index(
                int(first),
                regular_sources.shape,
            )
            second_vertex = np.unravel_index(
                int(second),
                regular_sources.shape,
            )
            inspected_edges.add(tuple(sorted((first_vertex, second_vertex))))
    xy, transition_diagnostics = _fit_source_transitions(
        regular_xy,
        regular_sources,
        case,
        replay,
        spacing,
        movable_vertices,
        inspected_edges,
    )
    height, sources, fitted_diagnostics = top_connected_height(xy, case, replay)
    points = np.column_stack((xy.reshape(-1, 2), height.reshape(-1)))
    cell_faces, corners, _, center_diagnostics = _structured_cell_faces(
        xy,
        points,
        case,
        replay,
    )
    quality, angles, areas = _triangle_quality_values(
        points,
        cell_faces.reshape(-1, 3),
    )
    bad_faces = (
        ~np.isfinite(quality)
        | ~np.isfinite(angles)
        | (quality < QUALITY_MIN_Q)
        | (angles < QUALITY_MIN_ANGLE_DEG)
        | (areas <= 1e-12)
    )
    bad_cells = np.any(bad_faces.reshape(-1, 2), axis=1)

    split_edges = set()
    for cell_index in np.flatnonzero(bad_cells):
        lower_left, lower_right, upper_right, upper_left = corners[cell_index]
        horizontal = (
            np.linalg.norm(points[lower_right] - points[lower_left])
            + np.linalg.norm(points[upper_right] - points[upper_left])
        ) / 2.0
        vertical = (
            np.linalg.norm(points[upper_left] - points[lower_left])
            + np.linalg.norm(points[upper_right] - points[lower_right])
        ) / 2.0
        if horizontal >= vertical:
            split_edges.add(tuple(sorted((lower_left, lower_right))))
            split_edges.add(tuple(sorted((upper_left, upper_right))))
        else:
            split_edges.add(tuple(sorted((lower_left, upper_left))))
            split_edges.add(tuple(sorted((lower_right, upper_right))))

    point_rows = points.tolist()
    source_rows = sources.reshape(-1).tolist()
    midpoint_indices = {}
    midpoint_parent_edges = []
    for edge in sorted(split_edges):
        middle_xy = (
            np.asarray(point_rows[edge[0]][:2])
            + np.asarray(point_rows[edge[1]][:2])
        ) / 2.0
        middle_height, middle_source, _ = top_connected_height(
            middle_xy[None, :],
            case,
            replay,
        )
        midpoint_indices[edge] = len(point_rows)
        point_rows.append(
            [middle_xy[0], middle_xy[1], float(middle_height[0])]
        )
        source_rows.append(int(middle_source[0]))
        midpoint_parent_edges.append([int(edge[0]), int(edge[1])])

    output_faces = []
    locally_refined_cells = 0
    post_refinement_bad_cells = 0
    for cell_index, cell_corners in enumerate(corners):
        polygon = []
        for first, second in zip(
            cell_corners,
            np.roll(cell_corners, -1),
        ):
            polygon.append(int(first))
            midpoint = midpoint_indices.get(tuple(sorted((first, second))))
            if midpoint is not None:
                polygon.append(midpoint)
        if len(polygon) == 4:
            output_faces.extend(cell_faces[cell_index].tolist())
            continue
        locally_refined_cells += 1
        score, triangulation = _best_polygon_triangulation(
            polygon,
            point_rows,
        )
        output_faces.extend(triangulation)
        post_refinement_bad_cells += score < 1.0

    points = np.asarray(point_rows, dtype=np.float64)
    faces = np.asarray(output_faces, dtype=np.int64)
    mesh = pv.PolyData(
        points,
        np.column_stack((np.full(len(faces), 3, dtype=np.int64), faces)),
    )
    mesh.point_data["source_index"] = np.asarray(source_rows, dtype=np.int32)
    diagnostics.update(fitted_diagnostics)
    diagnostics.update(transition_diagnostics)
    diagnostics.update(
        {
            "grid_dimensions_xy": [len(x), len(y)],
            "spacing_mm": float(spacing),
            "cell_center_sample_count": center_diagnostics["sample_count"],
            "cell_center_internal_cavity_sample_count": center_diagnostics[
                "internal_cavity_sample_count"
            ],
            "all_removed_intervals_top_connected": (
                diagnostics["all_removed_intervals_top_connected"]
                and fitted_diagnostics["all_removed_intervals_top_connected"]
                and center_diagnostics["all_removed_intervals_top_connected"]
            ),
            "generation_policy": (
                "只在原候选质量失败单元内，将邻近格点吸附到连续来源"
                "切换线；仍失败的单元沿三维长方向插入共享解析中点；"
                "局部剖分最大化最差三角质量"
            ),
            "pre_alignment_bad_cells": int(
                np.count_nonzero(regular_bad_cells)
            ),
            "pre_refinement_bad_cells": int(np.count_nonzero(bad_cells)),
            "split_edge_count": len(split_edges),
            "inserted_midpoint_count": len(midpoint_indices),
            "inserted_midpoint_parent_edges": midpoint_parent_edges,
            "locally_refined_cell_count": locally_refined_cells,
            "post_refinement_bad_cells": int(post_refinement_bad_cells),
        }
    )
    return mesh, diagnostics


def _incident_minimum_quality(points, faces):
    quality, angles, areas = _triangle_quality_values(points, faces)
    normalized = np.minimum(
        quality / QUALITY_MIN_Q,
        angles / QUALITY_MIN_ANGLE_DEG,
    )
    normalized[areas <= 1e-12] = 0.0
    normalized[~np.isfinite(normalized)] = 0.0
    return float(np.min(normalized, initial=np.inf))


def _optimize_constraint_points(mesh, parent_edges, case, replay):
    """在父边上优化新增点，最大化其关联三角形的最差三维质量。"""
    points = np.asarray(mesh.points, dtype=np.float64).copy()
    faces = mesh.faces.reshape(-1, 4)[:, 1:].astype(np.int64, copy=False)
    base_point_count = len(points) - len(parent_edges)
    incident_faces = [[] for _ in range(len(points))]
    for face_index, face in enumerate(faces):
        for vertex in face:
            incident_faces[int(vertex)].append(face_index)

    optimized = set()
    final_parameters = {}
    completed_sweeps = 0
    score_before = _incident_minimum_quality(points, faces)
    source_indices = np.asarray(
        mesh.point_data["source_index"],
        dtype=np.int32,
    ).copy()
    for sweep in range(CONSTRAINT_OPTIMIZATION_SWEEPS):
        changed = False
        for offset, parent_edge in enumerate(parent_edges):
            point_index = base_point_count + offset
            first, second = map(int, parent_edge)
            start = points[first].copy()
            end = points[second].copy()
            local_faces = faces[incident_faces[point_index]]
            old_point = points[point_index].copy()
            old_source = int(source_indices[point_index])
            best_score = _incident_minimum_quality(points, local_faces)
            best_point = old_point
            best_source = old_source
            best_parameter = None
            low = 0.0
            high = 1.0
            for _ in range(CONSTRAINT_SEARCH_LEVELS):
                parameters = np.linspace(
                    low,
                    high,
                    CONSTRAINT_SEARCH_SAMPLES,
                )
                candidate_xy = (
                    start[None, :2]
                    + parameters[:, None] * (end - start)[None, :2]
                )
                heights, sources, _ = top_connected_height(
                    candidate_xy,
                    case,
                    replay,
                )
                level_best = None
                for parameter, xy_value, height, source in zip(
                    parameters,
                    candidate_xy,
                    heights,
                    sources,
                ):
                    points[point_index] = (
                        float(xy_value[0]),
                        float(xy_value[1]),
                        float(height),
                    )
                    score = _incident_minimum_quality(points, local_faces)
                    if score > best_score + 1e-12:
                        best_score = score
                        best_point = points[point_index].copy()
                        best_source = int(source)
                        best_parameter = float(parameter)
                    if level_best is None or score > level_best[0]:
                        level_best = (score, float(parameter))
                points[point_index] = best_point
                if level_best is None:
                    break
                step = (high - low) / (CONSTRAINT_SEARCH_SAMPLES - 1)
                low = max(0.0, level_best[1] - step)
                high = min(1.0, level_best[1] + step)
            points[point_index] = best_point
            source_indices[point_index] = best_source
            if best_parameter is not None:
                changed = True
                optimized.add(point_index)
                final_parameters[point_index] = best_parameter
        completed_sweeps = sweep + 1
        if not changed:
            break

    output = pv.PolyData(points, mesh.faces.copy())
    for name in mesh.point_data:
        output.point_data[name] = np.asarray(mesh.point_data[name]).copy()
    output.point_data["source_index"] = source_indices
    score_after = _incident_minimum_quality(points, faces)
    return output, {
        "constraint_optimization_policy": (
            "新增边点保持在父边XY参数线上，以解析高度映射到曲面；"
            "分层确定性搜索最大化关联三角形的最差三维质量"
        ),
        "constraint_search_samples_per_level": CONSTRAINT_SEARCH_SAMPLES,
        "constraint_search_levels": CONSTRAINT_SEARCH_LEVELS,
        "constraint_optimization_sweeps": completed_sweeps,
        "optimized_constraint_point_count": len(optimized),
        "constraint_point_min_parameter": float(
            min(final_parameters.values(), default=0.5)
        ),
        "constraint_point_max_parameter": float(
            max(final_parameters.values(), default=0.5)
        ),
        "normalized_minimum_quality_before_optimization": score_before,
        "normalized_minimum_quality_after_optimization": score_after,
    }


def source_constrained_height_surface(case, replay, xy_bounds, spacing):
    """v3：连续来源交线采用受约束三维质量优化，跳变则拒绝高度图。"""
    mesh, diagnostics = source_fitted_height_surface(
        case,
        replay,
        xy_bounds,
        spacing,
    )
    x = _axis(xy_bounds[:2], spacing)
    y = _axis(xy_bounds[2:], spacing)
    regular_xy = np.stack(np.meshgrid(x, y, indexing="ij"), axis=-1)
    global_transitions = _scan_grid_source_transitions(
        regular_xy,
        case,
        replay,
    )
    diagnostics.update(global_transitions)
    diagnostics["algorithm_version"] = "source_constrained_v3"
    if not global_transitions["global_source_transition_continuous"]:
        diagnostics.update(
            {
                "height_graph_supported": False,
                "source_transition_model": "non_single_valued_vertical_wall",
                "constraint_optimization_skipped": True,
                "constraint_rejection_reason": (
                    "来源切换存在非零单侧高度差，需显式生成垂直壁；"
                    "连续高度图候选不得跨越该跳变"
                ),
            }
        )
        return mesh, diagnostics

    optimized, optimization = _optimize_constraint_points(
        mesh,
        diagnostics["inserted_midpoint_parent_edges"],
        case,
        replay,
    )
    diagnostics.update(optimization)
    diagnostics.update(
        {
            "height_graph_supported": True,
            "source_transition_model": "continuous_feature_curve",
            "constraint_optimization_skipped": False,
            "generation_policy_v3": (
                "先沿用冻结v2的失败单元来源吸附与共边局部剖分，"
                "再将新增点约束在各自父边上，按解析曲面三维质量作"
                "确定性max-min优化；全网格检出高度跳变时拒绝候选"
            ),
        }
    )
    return optimized, diagnostics


def implicit_contour_surface(case, replay, xy_bounds, z_bounds, spacing):
    """用规则三维体素场和VTK contour提取普通工程基线。"""
    x = _axis(xy_bounds[:2], spacing)
    y = _axis(xy_bounds[2:], spacing)
    z = _axis(z_bounds, spacing)
    grid = pv.ImageData(
        dimensions=(len(x), len(y), len(z)),
        spacing=(spacing, spacing, spacing),
        origin=(x[0], y[0], z[0]),
    )
    started = perf_counter()
    grid.point_data["field"] = actual_material_field(grid.points, case, replay)
    mesh = grid.contour([0.0], scalars="field", method="contour").triangulate()
    elapsed_ms = (perf_counter() - started) * 1000.0
    return mesh, {
        "grid_dimensions_xyz": [len(x), len(y), len(z)],
        "spacing_mm": float(spacing),
        "elapsed_ms": elapsed_ms,
    }


def maintain_surface(
    mesh,
    target_length=0.12,
    iterations=3,
    feature_angle_deg=30.0,
    surface_budget=0.025,
):
    """复用既有各向同性重网格，对解析候选作固定参数质量维护。"""
    import pymeshlab as pm

    started = perf_counter()
    faces = np.asarray(mesh.faces).reshape(-1, 4)[:, 1:]
    mesh_set = pm.MeshSet()
    mesh_set.add_mesh(pm.Mesh(np.asarray(mesh.points), faces))
    mesh_set.meshing_remove_duplicate_vertices()
    mesh_set.meshing_remove_null_faces()
    mesh_set.meshing_isotropic_explicit_remeshing(
        iterations=iterations,
        targetlen=pm.PureValue(target_length),
        featuredeg=feature_angle_deg,
        checksurfdist=True,
        maxsurfdist=pm.PureValue(surface_budget),
        smoothflag=True,
    )
    maintained = mesh_set.current_mesh()
    maintained_faces = maintained.face_matrix()
    output = pv.PolyData(
        maintained.vertex_matrix(),
        np.column_stack(
            (
                np.full(len(maintained_faces), 3, dtype=np.int64),
                maintained_faces,
            )
        ),
    )
    return output, {
        "elapsed_ms": (perf_counter() - started) * 1000.0,
        "target_length_mm": float(target_length),
        "iterations": int(iterations),
        "feature_angle_deg": float(feature_angle_deg),
        "surface_budget_mm": float(surface_budget),
        "implementation": "PyMeshLab meshing_isotropic_explicit_remeshing",
    }


def mesh_topology(mesh):
    """检查开放曲面仍应满足的连通、流形边、绕序和自交条件。"""
    import pymeshlab as pm

    faces = np.asarray(mesh.faces).reshape(-1, 4)[:, 1:]
    directed = np.concatenate(
        (
            faces[:, [0, 1]],
            faces[:, [1, 2]],
            faces[:, [2, 0]],
        ),
        axis=0,
    )
    canonical = np.sort(directed, axis=1)
    _, inverse, counts = np.unique(
        canonical,
        axis=0,
        return_inverse=True,
        return_counts=True,
    )
    direction = np.where(directed[:, 0] < directed[:, 1], 1, -1)
    direction_sum = np.bincount(inverse, weights=direction)
    inconsistent = (counts == 2) & (direction_sum != 0)

    connectivity = mesh.connectivity()
    region_ids = np.asarray(connectivity.cell_data["RegionId"])
    component_count = int(np.max(region_ids, initial=-1) + 1)

    mesh_set = pm.MeshSet()
    mesh_set.add_mesh(pm.Mesh(np.asarray(mesh.points), faces))
    mesh_set.compute_selection_by_self_intersections_per_face()
    self_intersections = int(mesh_set.current_mesh().selected_face_number())
    return {
        "connected_components": component_count,
        "boundary_edges": int(np.count_nonzero(counts == 1)),
        "non_manifold_edges": int(np.count_nonzero(counts > 2)),
        "inconsistent_interior_edges": int(np.count_nonzero(inconsistent)),
        "self_intersection_faces": self_intersections,
    }


def mesh_quality(mesh):
    """按共同门槛统计三角形质量；开放ROI边界单独报告。"""
    faces = np.asarray(mesh.faces).reshape(-1, 4)[:, 1:]
    quality, minimum_angle, areas = _triangle_quality_values(
        np.asarray(mesh.points, dtype=np.float64),
        faces,
    )
    bad = (
        ~np.isfinite(quality)
        | ~np.isfinite(minimum_angle)
        | (quality < QUALITY_MIN_Q)
        | (minimum_angle < QUALITY_MIN_ANGLE_DEG)
        | (areas <= 1e-12)
    )
    return {
        "vertices": int(mesh.n_points),
        "faces": int(mesh.n_cells),
        "bad_faces": int(np.count_nonzero(bad)),
        "min_q": float(np.min(quality, initial=np.inf)),
        "min_angle_deg": float(np.min(minimum_angle, initial=np.inf)),
        "boundary_edges": int(mesh.n_open_edges),
        "quality_gate": {
            "min_q": QUALITY_MIN_Q,
            "min_angle_deg": QUALITY_MIN_ANGLE_DEG,
        },
    }


def _face_centers(mesh):
    faces = np.asarray(mesh.faces).reshape(-1, 4)[:, 1:]
    return np.asarray(mesh.points, dtype=np.float64)[faces].mean(axis=1)


def _distance_summary(distances):
    distances = np.asarray(distances, dtype=np.float64)
    return {
        "max_mm": float(np.max(distances, initial=0.0)),
        "p95_mm": float(np.percentile(distances, 95)),
        "rms_mm": float(np.sqrt(np.mean(distances**2))),
        "samples": len(distances),
    }


def _distances_to_mesh(points, reference):
    cloud = pv.PolyData(np.asarray(points, dtype=np.float64))
    measured = cloud.compute_implicit_distance(reference, inplace=False)
    return np.abs(np.asarray(measured.point_data["implicit_distance"]))


def sampled_surface_audit(mesh, dense_target, case, replay):
    """以公共隐式场和密集解析采样审计，结果不是连续曲面严格证书。"""
    mesh_samples = np.vstack((np.asarray(mesh.points), _face_centers(mesh)))
    target_samples = np.asarray(dense_target.points)
    residual = np.abs(actual_material_field(mesh_samples, case, replay))
    return {
        "implicit_residual": _distance_summary(residual),
        "mesh_to_dense_target": _distance_summary(
            _distances_to_mesh(mesh_samples, dense_target)
        ),
        "dense_target_to_mesh": _distance_summary(
            _distances_to_mesh(target_samples, mesh)
        ),
        "interpretation": (
            "顶点和面心的抽样误差；dense_target也是解析高度的离散网格，"
            "这些数值不是连续曲面的严格上界证书"
        ),
    }
