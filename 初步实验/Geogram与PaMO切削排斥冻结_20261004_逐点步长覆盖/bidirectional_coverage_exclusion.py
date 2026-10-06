"""双向超差面共同触发局部细分，投影新增中点及超差原顶点，原门槛保持。"""

import numpy as np
import trimesh
from vtkmodules.vtkCommonDataModel import vtkStaticCellLocator
from vtkmodules.vtkCommonCore import reference as vtk_reference

from late_reverse_exclusion import late_reverse_exclusion
from adaptive_cut_exclusion import refine_faces
from audit_pamo_outputs import area_samples, as_polydata
from cut_exclusion import repair_cut_exclusion_many
from exact_embedding_gate import mesh_valid_full_embedding
from run_constrained_feedback import global_geometry
from geometry_preservation_audit import MeshDistance


def bidirectional_midpoint_seed(mesh, reference, tolerance=.1, step_fraction=1.):
    """参照顶点及固定面积样本只作细分触发，不作为连续距离证明。"""
    points = np.vstack((reference.vertices, area_samples(as_polydata(reference), 8192, 20260923)))
    locator = vtkStaticCellLocator()
    locator.SetDataSet(as_polydata(mesh))
    locator.BuildLocator()
    nearest, cell, sub, square = [0., 0., 0.], vtk_reference(0), vtk_reference(0), vtk_reference(0.)
    marked = np.zeros(len(mesh.faces), dtype=bool)
    deficits = []
    maximum = 0.
    for index, point in enumerate(points):
        locator.FindClosestPoint(point, nearest, cell, sub, square)
        distance = float(square) ** .5
        maximum = max(maximum, distance)
        if distance > tolerance:
            marked[int(cell)] = True
            deficits.append((distance, index, int(cell)))
    # 正向顶点和固定面积样本同样触发，避免只消除反向缺口后留下跨凹陷的面。
    target_locator = vtkStaticCellLocator()
    target_locator.SetDataSet(as_polydata(reference))
    target_locator.BuildLocator()
    distance_to_target = MeshDistance(as_polydata(reference))
    forward_vertices = distance_to_target(mesh.vertices)
    bad_vertices = np.flatnonzero(forward_vertices > tolerance)
    for vertex in bad_vertices:
        incident = mesh.vertex_faces[vertex]
        marked[incident[incident >= 0]] = True
    forward_samples = area_samples(as_polydata(mesh), 8192, 20260922)
    forward_errors = distance_to_target(forward_samples)
    for point in forward_samples[forward_errors > tolerance]:
        locator.FindClosestPoint(point, nearest, cell, sub, square)
        marked[int(cell)] = True
    record = {"trigger_mm": tolerance, "reference_vertices_and_area_samples": len(points),
              "uncovered_points": len(deficits), "marked_faces": int(marked.sum()),
              "reverse_probe_max_mm": maximum, "old_vertices_fixed_in_seed": False,
              "only_out_of_budget_old_vertices_may_move": True,
              "forward_bad_vertices": len(bad_vertices),
              "forward_bad_area_samples": int((forward_errors > tolerance).sum()),
              "continuous_distance_certified": False, "movement_CCD_certified": False}
    if not marked.any():
        record["reason"] = "no_bidirectional_probe_deficit"
        return mesh.copy(), record
    refined, refinement = refine_faces(mesh, marked)
    edges = {tuple(sorted((a, b))): index for index, a, b in refinement["midpoint_edges"]}
    selected = {}
    for distance, index, face_id in deficits:
        face = mesh.faces[face_id]
        available = [edges[tuple(sorted((int(face[i]), int(face[(i + 1) % 3]))))] for i in range(3)]
        vertex = min(available, key=lambda v: (float(np.linalg.norm(refined.vertices[v] - points[index])), v))
        if vertex not in selected or distance > selected[vertex][0]:
            selected[vertex] = (distance, index)
    vertices = refined.vertices.copy()
    owners = refined.vertex_faces
    accepted, rejected = [], 0
    proposals = []
    for vertex in list(bad_vertices) + list(range(len(mesh.vertices), len(refined.vertices))):
        target_locator.FindClosestPoint(vertices[vertex], nearest, cell, sub, square)
        proposals.append((int(vertex), np.asarray(nearest).copy(), "forward_projection"))
    for vertex, (distance, index) in sorted(selected.items(), key=lambda item: (-item[1][0], item[0])):
        proposals.append((vertex, points[index], "reverse_target"))
    for vertex, target_point, reason in proposals:
        # 默认完整提案保持旧坐标；新显式步长在法向筛选之前缩短每个点的移动。
        if step_fraction != 1.:
            target_point = vertices[vertex] + step_fraction * (target_point - vertices[vertex])
        incident = owners[vertex]
        incident = incident[incident >= 0]
        faces = refined.faces[incident]
        before = vertices[faces]
        after = before.copy()
        after[faces == vertex] = target_point
        old_normal = np.cross(before[:, 1] - before[:, 0], before[:, 2] - before[:, 0])
        new_normal = np.cross(after[:, 1] - after[:, 0], after[:, 2] - after[:, 0])
        # 浮点法向检查只筛提案；终态仍必须通过原全量嵌入、面积、排斥及距离门槛。
        if np.any(np.einsum("ij,ij->i", old_normal, new_normal) <= 0):
            rejected += 1
            continue
        vertices[vertex] = target_point
        accepted.append({"vertex": int(vertex), "reason": reason, "new_midpoint": bool(vertex >= len(mesh.vertices))})
    record.update(projection_step_fraction=step_fraction, refinement=refinement, selected=accepted, accepted_projection_or_target_proposals=len(accepted),
                  rejected_orientation_proposals=rejected)
    fixed = np.ones(len(mesh.vertices), dtype=bool)
    fixed[bad_vertices] = False
    if not np.array_equal(vertices[:len(mesh.vertices)][fixed], mesh.vertices[fixed]):
        raise ValueError("双向覆盖提案改动了未超差原顶点")
    return trimesh.Trimesh(vertices, refined.faces.copy(), process=False), record


def bidirectional_coverage_exclusion(raw, tools, reference, anchor_classifier):
    captured = {}
    def remember(mesh, tool, normals, offsets):
        result = anchor_classifier(mesh, tool, normals, offsets)
        digest = result.get("classification", {}).get("saved_mesh_sha256")
        if digest and digest not in captured:
            captured[digest] = mesh.copy()
        return result

    mesh, record = late_reverse_exclusion(raw, tools, reference, remember)
    record.update(extra_local_coverage_rounds_budget=2, coverage_bidirectional_marking=True,
                  coverage_movable_vertices="new_midpoints_and_forward_out_of_budget_old_vertices")
    if record["accepted"]:
        return mesh, record
    legal = [a for a in record["attempts"] if a["exclusion"]["accepted"] and a["mesh_valid"]]
    if not legal:
        record["coverage_reason"] = "no_legal_embedded_base"
        return mesh, record
    best = min(legal, key=lambda a: a["geometry"]["probe_max_mm"])
    anchors = best["exclusion"]["outside_anchor_certificate"]
    anchor = anchors if isinstance(anchors, dict) else anchors[0]
    working = captured[anchor["classification"]["saved_mesh_sha256"]]
    for round_index in range(2):
        seed, coverage = bidirectional_midpoint_seed(working, reference)
        if not coverage["marked_faces"]:
            record["coverage_reason"] = "no_bidirectional_probe_deficit"
            break
        candidate, details = repair_cut_exclusion_many(seed, tools, target_vertices=seed.vertices,
                                                       anchor_classifier=remember)
        valid, checks = False, {}
        if details["accepted"]:
            anchors = details["outside_anchor_certificate"]
            anchor = anchors if isinstance(anchors, dict) else anchors[0]
            valid, checks = mesh_valid_full_embedding(candidate, anchor["classification"])
        geometry = global_geometry(candidate, reference)
        record["attempts"].append({"level": "local_coverage_" + str(round_index), "coverage_midpoints": coverage,
            "exclusion": details, "mesh_valid": valid, "checks": checks, "geometry": geometry,
            "vertices": len(candidate.vertices), "faces": len(candidate.faces)})
        if details["accepted"] and valid and geometry["probe_max_mm"] <= .1:
            record.update(accepted=True, selected_level=len(record["attempts"]) - 1)
            return candidate, record
        if not details["accepted"] or not valid:
            record["coverage_reason"] = "new_patch_failed_original_legality_gates"
            break
        working = candidate
    return mesh, record
