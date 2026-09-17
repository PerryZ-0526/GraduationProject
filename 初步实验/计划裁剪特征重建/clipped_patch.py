"""计划圆柱裁剪下的轴对称扫掠曲面生成与独立验收。"""
from dataclasses import dataclass
from pathlib import Path
import sys

import numpy as np
import trimesh


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "真实骨面共边拼接"))
from pymeshlab_isolation import self_intersection_flags


class Rejected(ValueError):
    """输入不属于当前解析模型或候选未满足显式约束。"""


@dataclass(frozen=True)
class TargetProfile:
    """竖直球扫掠与计划圆柱裁剪后的有限旋转曲面。"""

    center_z: float
    tool_radius: float
    clip_radius: float
    outer_radius: float
    theta_end: float
    mouth_radius: float
    clip_active: bool
    wall_kind: str | None
    wall_bottom_z: float | None
    features: tuple[dict, ...]


@dataclass
class Candidate:
    """带曲面来源和显式特征环的开放局部网格。"""

    mesh: trimesh.Trimesh
    face_sources: np.ndarray
    profile: TargetProfile
    feature_rings: dict[str, np.ndarray]
    outer_ring: np.ndarray


def target_profile(center_z, tool_radius=2.9, clip_radius=2.5, outer_radius=4.0):
    """构造半空间z<=0中竖直球扫掠经计划圆柱裁剪后的解析剖面。"""
    values = np.asarray([center_z, tool_radius, clip_radius, outer_radius], dtype=np.float64)
    if not np.isfinite(values).all():
        raise Rejected("尺寸必须为有限数")
    center_z, tool_radius, clip_radius, outer_radius = map(float, values)
    if tool_radius <= 0 or clip_radius <= 0 or outer_radius <= clip_radius:
        raise Rejected("半径必须为正，且外边界必须大于裁剪半径")
    if center_z >= tool_radius:
        raise Rejected("无接触或相切状态不生成凹坑")

    natural_mouth = (
        float(np.sqrt(max(tool_radius**2 - center_z**2, 0.0)))
        if center_z >= 0
        else tool_radius
    )
    tolerance = 32 * np.finfo(np.float64).eps * max(
        1.0, abs(center_z), tool_radius, clip_radius, outer_radius
    )
    clip_active = clip_radius < natural_mouth - tolerance
    features = []

    if clip_active:
        theta_end = float(np.arcsin(clip_radius / tool_radius))
        mouth_radius = clip_radius
        wall_kind = "plan_clip"
        wall_bottom_z = center_z - tool_radius * np.cos(theta_end)
        feature_angle = float(np.degrees(np.arccos(clip_radius / tool_radius)))
        features.append(
            {
                "name": "sphere_plan_clip",
                "sources": ("sphere", "plan_clip"),
                "radius": mouth_radius,
                "z": float(wall_bottom_z),
                "angle_deg": feature_angle,
                "preserved": True,
            }
        )
        features.append(
            {
                "name": "plan_clip_plane",
                "sources": ("plan_clip", "plane"),
                "radius": mouth_radius,
                "z": 0.0,
                "angle_deg": 90.0,
                "preserved": True,
            }
        )
    elif center_z < 0:
        theta_end = np.pi / 2
        mouth_radius = tool_radius
        wall_kind = "sweep_cylinder"
        wall_bottom_z = center_z
        features.append(
            {
                "name": "sphere_sweep_cylinder",
                "sources": ("sphere", "sweep_cylinder"),
                "radius": mouth_radius,
                "z": wall_bottom_z,
                "angle_deg": 0.0,
                "preserved": False,
            }
        )
        features.append(
            {
                "name": "sweep_cylinder_plane",
                "sources": ("sweep_cylinder", "plane"),
                "radius": mouth_radius,
                "z": 0.0,
                "angle_deg": 90.0,
                "preserved": True,
            }
        )
    else:
        theta_end = float(np.arccos(center_z / tool_radius))
        mouth_radius = natural_mouth
        wall_kind = None
        wall_bottom_z = None
        features.append(
            {
                "name": "sphere_plane",
                "sources": ("sphere", "plane"),
                "radius": mouth_radius,
                "z": 0.0,
                "angle_deg": float(np.degrees(theta_end)),
                "preserved": True,
            }
        )

    if outer_radius <= mouth_radius + tolerance:
        raise Rejected("外边界必须严格包围实际坑口")
    return TargetProfile(
        center_z=center_z,
        tool_radius=tool_radius,
        clip_radius=clip_radius,
        outer_radius=outer_radius,
        theta_end=float(theta_end),
        mouth_radius=float(mouth_radius),
        clip_active=bool(clip_active),
        wall_kind=wall_kind,
        wall_bottom_z=None if wall_bottom_z is None else float(wall_bottom_z),
        features=tuple(features),
    )


def cumulative_center(center_positions):
    """同轴单调扫掠的最终下边界只由最低球心决定，重复和顺序不改变目标。"""
    centers = np.asarray(center_positions, dtype=np.float64)
    if centers.ndim != 1 or not len(centers) or not np.isfinite(centers).all():
        raise Rejected("球心序列必须是一维非空有限数组")
    return float(np.min(centers))


def _connect(inner, outer):
    """按周向事件连接相邻环，允许环顶点数随半径变化。"""
    n, m = len(inner), len(outer)
    faces = []
    i = j = 0
    while i < n or j < m:
        if i < n and (j == m or (i + 1) * m <= (j + 1) * n):
            faces.append([inner[i % n], outer[j % m], inner[(i + 1) % n]])
            i += 1
        else:
            faces.append([inner[i % n], outer[j % m], outer[(j + 1) % m]])
            j += 1
    return faces


def _sample_interval(start, end, spacing):
    length = abs(end - start)
    count = max(1, int(np.ceil(length / spacing)))
    return np.linspace(start, end, count + 1)[1:]


def generate(
    center_z,
    tool_radius=2.9,
    clip_radius=2.5,
    outer_radius=4.0,
    spacing=0.25,
    preserve_smooth_seam=False,
):
    """生成解析开放面；真实折线共边，C1接缝默认不强制成环。"""
    if not np.isfinite(spacing) or spacing <= 0:
        raise Rejected("采样间距必须为有限正数")
    profile = target_profile(center_z, tool_radius, clip_radius, outer_radius)
    points = []

    if profile.wall_kind == "sweep_cylinder" and not preserve_smooth_seam:
        sphere_length = tool_radius * profile.theta_end
        wall_length = -center_z
        for arc in _sample_interval(0.0, sphere_length + wall_length, spacing):
            if arc < sphere_length:
                theta = arc / tool_radius
                points.append(
                    {
                        "r": tool_radius * np.sin(theta),
                        "z": center_z - tool_radius * np.cos(theta),
                        "source": "sphere",
                        "feature": None,
                    }
                )
            else:
                points.append(
                    {
                        "r": tool_radius,
                        "z": center_z + arc - sphere_length,
                        "source": "sweep_cylinder",
                        "feature": None,
                    }
                )
        points[-1]["feature"] = "sweep_cylinder_plane"
    else:
        sphere_length = tool_radius * profile.theta_end
        for arc in _sample_interval(0.0, sphere_length, spacing):
            theta = arc / tool_radius
            points.append(
                {
                    "r": tool_radius * np.sin(theta),
                    "z": center_z - tool_radius * np.cos(theta),
                    "source": "sphere",
                    "feature": None,
                }
            )
        if profile.wall_kind is None:
            points[-1]["feature"] = "sphere_plane"
        else:
            first_feature = (
                "sphere_plan_clip"
                if profile.wall_kind == "plan_clip"
                else "sphere_sweep_cylinder"
            )
            points[-1]["feature"] = first_feature
            wall_values = _sample_interval(profile.wall_bottom_z, 0.0, spacing)
            for z in wall_values:
                points.append(
                    {
                        "r": profile.mouth_radius,
                        "z": float(z),
                        "source": profile.wall_kind,
                        "feature": None,
                    }
                )
            points[-1]["feature"] = f"{profile.wall_kind}_plane"

    for radius in _sample_interval(profile.mouth_radius, outer_radius, spacing):
        points.append(
            {
                "r": float(radius),
                "z": 0.0,
                "source": "plane",
                "feature": None,
            }
        )

    vertices = [[0.0, 0.0, center_z - tool_radius]]
    faces = []
    face_sources = []
    feature_rings = {}
    previous = None
    previous_source = "sphere"
    for point in points:
        radius = point["r"]
        ring_size = 6 * max(1, int(round(2 * np.pi * radius / (6 * spacing))))
        angles = np.arange(ring_size) * 2 * np.pi / ring_size
        current = np.arange(len(vertices), len(vertices) + ring_size, dtype=np.int64)
        vertices.extend(
            np.column_stack(
                [
                    radius * np.cos(angles),
                    radius * np.sin(angles),
                    np.full(ring_size, point["z"]),
                ]
            ).tolist()
        )
        if previous is None:
            added = [[0, current[j], current[(j + 1) % ring_size]] for j in range(ring_size)]
        else:
            added = _connect(previous, current)
        source = point["source"] if point["source"] == previous_source else f"{previous_source}+{point['source']}"
        faces.extend(added)
        face_sources.extend([source] * len(added))
        if point["feature"] is not None:
            feature_rings[point["feature"]] = current.copy()
        previous = current
        previous_source = point["source"]

    mesh = trimesh.Trimesh(
        np.asarray(vertices, dtype=np.float64),
        np.asarray(faces, dtype=np.int64),
        process=False,
    )
    return Candidate(
        mesh=mesh,
        face_sources=np.asarray(face_sources),
        profile=profile,
        feature_rings=feature_rings,
        outer_ring=previous.copy(),
    )


def exact_distance(points, profile):
    """计算点到有限解析目标曲面并集的精确欧氏距离。"""
    points = np.asarray(points, dtype=np.float64)
    original_shape = points.shape[:-1]
    points = points.reshape(-1, 3)
    rho = np.linalg.norm(points[:, :2], axis=1)
    z = points[:, 2]

    theta = np.clip(
        np.arctan2(rho, profile.center_z - z),
        0.0,
        profile.theta_end,
    )
    sphere = np.hypot(
        rho - profile.tool_radius * np.sin(theta),
        z - profile.center_z + profile.tool_radius * np.cos(theta),
    )
    distances = [sphere]
    if profile.wall_kind is not None:
        wall = np.hypot(
            rho - profile.mouth_radius,
            z - np.clip(z, profile.wall_bottom_z, 0.0),
        )
        distances.append(wall)
    plane = np.hypot(
        rho - np.clip(rho, profile.mouth_radius, profile.outer_radius),
        z,
    )
    distances.append(plane)
    return np.min(np.vstack(distances), axis=0).reshape(original_shape)


def _mesh_quality(mesh):
    triangles = mesh.triangles
    edges = np.roll(triangles, -1, axis=1) - triangles
    lengths = np.linalg.norm(edges, axis=2)
    area = np.linalg.norm(np.cross(edges[:, 0], -edges[:, 2]), axis=1) / 2
    denominator = np.sum(lengths**2, axis=1)
    q = np.divide(
        4 * np.sqrt(3) * area,
        denominator,
        out=np.zeros_like(area),
        where=denominator > 0,
    )
    angles = []
    for index in range(3):
        a = -edges[:, (index - 1) % 3]
        b = edges[:, index]
        norm = np.linalg.norm(a, axis=1) * np.linalg.norm(b, axis=1)
        cosine = np.divide(
            np.sum(a * b, axis=1),
            norm,
            out=np.ones_like(norm),
            where=norm > 0,
        )
        angles.append(np.degrees(np.arccos(np.clip(cosine, -1, 1))))
    minimum = np.min(angles, axis=0)
    return {
        "min_angle_deg": float(np.min(minimum)),
        "min_q": float(np.min(q)),
        "degenerate": int(np.count_nonzero(area <= 1e-12)),
        "bad_faces": int(np.count_nonzero((minimum < 25.0) | (q < 0.4) | ~np.isfinite(q))),
    }


def _candidate_to_target_bound(mesh, profile, cover=0.04):
    maximum = 0.0
    sample_count = 0
    for triangle in mesh.triangles:
        edge = float(
            np.max(
                np.linalg.norm(
                    triangle - np.roll(triangle, 1, axis=0),
                    axis=1,
                )
            )
        )
        subdivisions = max(1, int(np.ceil(edge / cover)))
        barycentric = np.asarray(
            [
                (i / subdivisions, j / subdivisions, 1 - (i + j) / subdivisions)
                for i in range(subdivisions + 1)
                for j in range(subdivisions + 1 - i)
            ]
        )
        samples = barycentric @ triangle
        sampled = float(np.max(exact_distance(samples, profile), initial=0.0))
        maximum = max(maximum, sampled + edge / subdivisions)
        sample_count += len(samples)
    return maximum, sample_count


def _ring_samples(radii, z_values, spacing):
    """在一组同轴环上按统一周向间距采样。"""
    radii = np.asarray(radii, dtype=np.float64)
    z_values = np.asarray(z_values, dtype=np.float64)
    if radii.shape != z_values.shape:
        raise ValueError("环半径与高度数量必须一致")
    count = max(12, int(np.ceil(2 * np.pi * float(np.max(radii)) / spacing)))
    phi = np.arange(count) * 2 * np.pi / count
    rr, pp = np.meshgrid(radii, phi, indexing="ij")
    zz, _ = np.meshgrid(z_values, phi, indexing="ij")
    points = np.column_stack(
        [rr.ravel() * np.cos(pp).ravel(), rr.ravel() * np.sin(pp).ravel(), zz.ravel()]
    )
    return points, 2 * np.pi / count


def _target_strata(profile, cover):
    strata = []
    theta_count = max(1, int(np.ceil(profile.tool_radius * profile.theta_end / cover)))
    theta = np.linspace(0.0, profile.theta_end, theta_count + 1)
    radius = profile.tool_radius * np.sin(theta)
    z = profile.center_z - profile.tool_radius * np.cos(theta)
    sphere_points, dphi = _ring_samples(radius, z, cover)
    sphere_cover = profile.tool_radius * (profile.theta_end / theta_count) / 2
    sphere_cover += profile.mouth_radius * dphi / 2
    strata.append(("sphere", sphere_points, sphere_cover))

    if profile.wall_kind is not None:
        length = -profile.wall_bottom_z
        z_count = max(1, int(np.ceil(length / cover)))
        z_values = np.linspace(profile.wall_bottom_z, 0.0, z_count + 1)
        wall_points, dphi = _ring_samples(
            np.full_like(z_values, profile.mouth_radius), z_values, cover
        )
        wall_cover = length / z_count / 2 + profile.mouth_radius * dphi / 2
        strata.append((profile.wall_kind, wall_points, wall_cover))

    radial_length = profile.outer_radius - profile.mouth_radius
    radial_count = max(1, int(np.ceil(radial_length / cover)))
    radii = np.linspace(profile.mouth_radius, profile.outer_radius, radial_count + 1)
    plane_points, dphi = _ring_samples(radii, np.zeros_like(radii), cover)
    plane_cover = radial_length / radial_count / 2 + profile.outer_radius * dphi / 2
    strata.append(("plane", plane_points, plane_cover))
    return strata


def _closest_distance(mesh, points, batch=50_000):
    maximum = 0.0
    for start in range(0, len(points), batch):
        _, distance, _ = trimesh.proximity.closest_point(mesh, points[start : start + batch])
        maximum = max(maximum, float(np.max(distance, initial=0.0)))
    return maximum


def _target_to_candidate_bound(mesh, profile, cover=0.04):
    maximum = 0.0
    sample_count = 0
    strata = {}
    for name, points, coverage in _target_strata(profile, cover):
        sampled = _closest_distance(mesh, points)
        bound = sampled + coverage
        strata[name] = {
            "sampled_max_mm": sampled,
            "cover_radius_mm": float(coverage),
            "upper_bound_mm": float(bound),
            "samples": len(points),
        }
        maximum = max(maximum, bound)
        sample_count += len(points)
    return maximum, sample_count, strata


def _edge_counts(faces):
    edges = np.sort(
        np.vstack([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]]),
        axis=1,
    )
    unique, counts = np.unique(edges, axis=0, return_counts=True)
    return {tuple(map(int, edge)): int(count) for edge, count in zip(unique, counts)}


def _component_count(faces):
    """用并查集统计引用顶点连通分量，避免引入额外图依赖。"""
    referenced = np.unique(faces)
    parent = {int(index): int(index) for index in referenced}

    def find(index):
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(a, b):
        root_a, root_b = find(a), find(b)
        if root_a != root_b:
            parent[root_b] = root_a

    for face in faces:
        union(int(face[0]), int(face[1]))
        union(int(face[1]), int(face[2]))
    return len({find(index) for index in parent})


def audit_candidate(
    candidate,
    error_limit=0.1,
    min_angle=25.0,
    min_q=0.4,
    certificate_spacing=0.04,
):
    """联合检查质量、开放盘拓扑、特征共边、自交及双向距离上界。"""
    mesh = candidate.mesh
    quality = _mesh_quality(mesh)
    edges = _edge_counts(mesh.faces)
    boundary = [edge for edge, count in edges.items() if count == 1]
    boundary_vertices = np.unique(boundary)
    degrees = {int(index): 0 for index in boundary_vertices}
    for a, b in boundary:
        degrees[a] += 1
        degrees[b] += 1
    one_boundary_loop = bool(
        len(boundary)
        and len(boundary) == len(boundary_vertices)
        and all(value == 2 for value in degrees.values())
    )
    outer = mesh.vertices[boundary_vertices]
    outer_boundary_ok = bool(
        np.allclose(outer[:, 2], 0.0, atol=1e-12, rtol=0)
        and np.allclose(
            np.linalg.norm(outer[:, :2], axis=1),
            candidate.profile.outer_radius,
            atol=1e-12,
            rtol=0,
        )
    )

    missing_feature_edges = 0
    nonmanifold_feature_edges = 0
    expected_features = {
        feature["name"]: feature
        for feature in candidate.profile.features
        if feature["preserved"]
    }
    feature_name_mismatch = set(candidate.feature_rings) != set(expected_features)
    feature_geometry_max = 0.0
    for name, ring in candidate.feature_rings.items():
        expected = expected_features.get(name)
        if expected is not None:
            vertices = mesh.vertices[ring]
            feature_geometry_max = max(
                feature_geometry_max,
                float(
                    np.max(
                        np.abs(
                            np.column_stack(
                                [
                                    np.linalg.norm(vertices[:, :2], axis=1)
                                    - expected["radius"],
                                    vertices[:, 2] - expected["z"],
                                ]
                            )
                        ),
                        initial=0.0,
                    )
                ),
            )
        for index in range(len(ring)):
            edge = tuple(sorted((int(ring[index]), int(ring[(index + 1) % len(ring)]))))
            count = edges.get(edge, 0)
            missing_feature_edges += count == 0
            nonmanifold_feature_edges += count != 2

    forward, forward_samples = _candidate_to_target_bound(
        mesh, candidate.profile, certificate_spacing
    )
    reverse, reverse_samples, reverse_strata = _target_to_candidate_bound(
        mesh, candidate.profile, certificate_spacing
    )
    intersection_count = int(
        np.count_nonzero(self_intersection_flags(mesh.vertices, mesh.faces))
    )
    connected = _component_count(mesh.faces) == 1
    reasons = []
    if quality["min_angle_deg"] < min_angle or quality["min_q"] < min_q:
        reasons.append("shape_quality")
    if quality["degenerate"]:
        reasons.append("degenerate_faces")
    if not mesh.is_winding_consistent:
        reasons.append("winding")
    if mesh.euler_number != 1 or not connected or not one_boundary_loop or not outer_boundary_ok:
        reasons.append("open_disk_topology")
    if (
        feature_name_mismatch
        or feature_geometry_max > 1e-10
        or missing_feature_edges
        or nonmanifold_feature_edges
    ):
        reasons.append("feature_curve_connectivity")
    if intersection_count:
        reasons.append("self_intersection")
    if forward > error_limit or reverse > error_limit:
        reasons.append("bidirectional_error")

    return {
        "vertices": len(mesh.vertices),
        "faces": len(mesh.faces),
        **quality,
        "winding": bool(mesh.is_winding_consistent),
        "euler": int(mesh.euler_number),
        "connected": bool(connected),
        "boundary_edges": len(boundary),
        "one_boundary_loop": one_boundary_loop,
        "outer_boundary_ok": outer_boundary_ok,
        "feature_count": len(candidate.feature_rings),
        "expected_feature_names": sorted(expected_features),
        "feature_name_mismatch": feature_name_mismatch,
        "feature_geometry_max_mm": feature_geometry_max,
        "missing_feature_edges": int(missing_feature_edges),
        "nonmanifold_feature_edges": int(nonmanifold_feature_edges),
        "self_intersection_faces": intersection_count,
        "mesh_to_target_upper_mm": float(forward),
        "target_to_mesh_upper_mm": float(reverse),
        "mesh_to_target_samples": forward_samples,
        "target_to_mesh_samples": reverse_samples,
        "target_to_mesh_strata": reverse_strata,
        "error_limit_mm": float(error_limit),
        "certificate_spacing_mm": float(certificate_spacing),
        "accepted": not reasons,
        "reasons": reasons,
    }
