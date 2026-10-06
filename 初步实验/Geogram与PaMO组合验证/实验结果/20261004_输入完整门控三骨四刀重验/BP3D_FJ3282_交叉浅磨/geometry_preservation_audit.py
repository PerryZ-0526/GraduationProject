"""连续组合的区域漂移、重复磨削及自适应距离区间检查。"""

import numpy as np
import trimesh
import pymeshlab as pm
from vtkmodules.vtkCommonDataModel import vtkStaticCellLocator
from vtkmodules.vtkCommonCore import reference

from audit_followup_candidate import quality_distribution
from audit_pamo_outputs import as_polydata, area_samples, reference_audit
from preflight_geogram_prefixes import metrics
from motion_record import capsule_field, replay_case


def replay_primitives(route, event):
    if route["body"] != "ct":
        return replay_case(route, {"late_event": "reject", "max_link_gap_ms": 200,
                                   "interpolate_missing_motion": False}, event)["primitives"]
    result = []
    for e in route["events"]:
        result.append({"start": np.array(e["explicit_sweep_start_mm"]),
                       "end": np.array(e["position_mm"]), "radius": e.get("tool_radius_mm", route["tool"]["radius_mm"])})
        if e["id"] == event:
            break
    return result


def clearance(points, primitives):
    return np.min(np.stack([capsule_field(points, p) for p in primitives]), axis=0)


class MeshDistance:
    """使用实际三角面最近点距离，避免把法向符号值当作距离上界。"""
    def __init__(self, mesh):
        self.locator = vtkStaticCellLocator()
        self.locator.SetDataSet(mesh)
        self.locator.BuildLocator()

    def __call__(self, points):
        closest, cid, sid, square = [0.0] * 3, reference(0), reference(0), reference(0.0)
        result = np.empty(len(points))
        for i, p in enumerate(points):
            self.locator.FindClosestPoint(p, closest, cid, sid, square)
            result[i] = np.sqrt(float(square))
        return result


def directed_interval(source, target, tolerance=0.01, max_cells=200000, decision_budget=0.1):
    """按距离函数1-Lipschitz性质细分源三角面；浮点查询误差尚未认证。"""
    cells = np.asarray(source.points)[np.asarray(source.faces).reshape(-1, 4)[:, 1:]]
    query = MeshDistance(target)
    vertices = np.asarray(source.points)
    vertex_dist = query(vertices)
    lower = float(vertex_dist.max())
    witness = vertices[int(vertex_dist.argmax())].tolist()
    evaluated = 0
    upper = None
    discarded_upper = 0.0
    while len(cells):
        center = cells.mean(axis=1)
        dist = query(center)
        radius = np.linalg.norm(cells - center[:, None, :], axis=2).max(axis=1)
        evaluated += len(cells)
        if float(dist.max()) > lower:
            lower = float(dist.max())
            witness = center[int(dist.argmax())].tolist()
        bounds = dist + radius
        upper = max(lower, float(bounds.max()), discarded_upper)
        if upper - lower <= tolerance or upper <= decision_budget or evaluated >= max_cells:
            break
        # 优先解决是否低于预算；已经安全的面片不为无关精度反复细分。
        threshold = decision_budget if 0 < decision_budget >= lower else lower + tolerance
        active = bounds > threshold
        if np.any(~active):
            discarded_upper = max(discarded_upper, float(bounds[~active].max()))
        keep = cells[active]
        if not len(keep):
            upper = max(lower, discarded_upper)
            break
        if evaluated + len(keep) * 4 > max_cells:
            break
        a, b, c = keep[:, 0], keep[:, 1], keep[:, 2]
        ab, bc, ca = (a + b) / 2, (b + c) / 2, (c + a) / 2
        cells = np.concatenate((np.stack((a, ab, ca), axis=1), np.stack((ab, b, bc), axis=1),
                                np.stack((ca, bc, c), axis=1), np.stack((ab, bc, ca), axis=1)))
    return {"lower_mm": lower, "upper_mm": upper, "lower_witness_xyz_mm": witness,
            "evaluated_cells": evaluated,
            "within_budget_under_exact_distance_assumption": bool(upper is not None and upper <= decision_budget),
            "floating_point_query_error_bound_mm": None,
            "certified_continuous_geometry": False}


def triangle_separation_gap(a, b):
    """若找到大于数值余量的投影间隙，两个三角形必不相交。"""
    ea, eb = np.roll(a, -1, axis=0) - a, np.roll(b, -1, axis=0) - b
    na, nb = np.cross(ea[0], ea[1]), np.cross(eb[0], eb[1])
    axes = [na, nb, *[np.cross(x, y) for x in ea for y in eb],
            *[np.cross(na, x) for x in ea], *[np.cross(nb, x) for x in eb]]
    gap = 0.0
    for axis in axes:
        norm = np.linalg.norm(axis)
        if norm <= 1e-14:
            continue
        pa, pb = a @ (axis / norm), b @ (axis / norm)
        gap = max(gap, float(pb.min() - pa.max()), float(pa.min() - pb.max()))
    return gap


def mesh_valid(mesh):
    m = metrics(mesh)
    m["self_intersection_raw_alarm_faces"] = m["self_intersection_faces"]
    # 检测器只给报警面集合；仅排除具有明确分离轴的面对，其余继续拒绝。
    if 1 < m["self_intersection_faces"] <= 200:
        detector = pm.MeshSet()
        detector.add_mesh(pm.Mesh(np.asarray(mesh.vertices), np.asarray(mesh.faces)))
        detector.compute_selection_by_self_intersections_per_face()
        ids = np.flatnonzero(detector.current_mesh().face_selection_array())
        unresolved = set()
        separated = []
        for n, first in enumerate(ids):
            for second in ids[n + 1:]:
                gap = triangle_separation_gap(mesh.triangles[first], mesh.triangles[second])
                if gap > 1e-9:
                    separated.append({"faces": [int(first), int(second)], "separation_gap_mm": gap})
                else:
                    unresolved.update((int(first), int(second)))
        m["self_intersection_faces"] = len(unresolved)
        m["separated_alarm_pairs"] = separated
        m["intersection_check_interpretation"] = "报警面集合内分离轴复核；非完整精确自交证书"
    # 按面邻接计数，不让分量统计隐式补洞或依赖可选networkx包。
    m["components"] = len(trimesh.graph.connected_components(mesh.face_adjacency,
        nodes=np.arange(len(mesh.faces)), engine="scipy"))
    valid = all((m["finite"], m["zero_area_faces"] == 0, m["watertight"],
                 m["winding_consistent"], m["vertex_manifold_closed"],
                 m["self_intersection_faces"] == 0))
    return valid, m


def preservation(mesh, initial, route, event, previous=None):
    """固定种子记录双向未切削区漂移；属于抽样证据而非区域不变证明。"""
    primitives = replay_primitives(route, event)
    points = area_samples(as_polydata(initial), 8192, 20261004)
    selected = clearance(points, primitives) >= 0.1
    distances = MeshDistance(as_polydata(mesh))(points[selected])
    reverse_points = area_samples(as_polydata(mesh), 8192, 20261005)
    reverse_selected = clearance(reverse_points, primitives) >= 0.1
    reverse = MeshDistance(as_polydata(initial))(reverse_points[reverse_selected])
    changed = clearance(mesh.triangles_center, primitives) <= 0.1
    roi = trimesh.Trimesh(mesh.vertices, mesh.faces[changed], process=False)
    result = {"uncut_margin_mm": 0.1, "initial_to_candidate_samples": int(selected.sum()),
              "candidate_to_initial_samples": int(reverse_selected.sum()),
              "uncut_sampled_max_mm": max(float(distances.max(initial=0)), float(reverse.max(initial=0))),
              "uncut_sampled_mean_mm": float(np.mean(np.concatenate((distances, reverse))))
                  if len(distances) + len(reverse) else None,
              "quality_all": quality_distribution(mesh), "quality_sweep_margin_roi": quality_distribution(roi)}
    if previous is not None:
        result["previous_mesh_sampled_difference"] = reference_audit(as_polydata(mesh), as_polydata(previous))
        result["previous_volume_delta_mm3"] = float(mesh.volume - previous.volume)
    return result
