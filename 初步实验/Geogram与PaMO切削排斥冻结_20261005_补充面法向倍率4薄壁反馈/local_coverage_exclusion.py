"""合法候选漏覆盖时，只细分最近面并移动新增中点，全部原门槛保持。"""

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


def coverage_midpoint_seed(mesh, reference, tolerance=.1):
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
    record = {"trigger_mm": tolerance, "reference_vertices_and_area_samples": len(points),
              "uncovered_points": len(deficits), "marked_faces": int(marked.sum()),
              "reverse_probe_max_mm": maximum, "old_vertices_fixed_in_seed": True,
              "continuous_distance_certified": False, "movement_CCD_certified": False}
    if not deficits:
        record["reason"] = "no_reverse_probe_deficit"
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
    for vertex, (distance, index) in sorted(selected.items(), key=lambda item: (-item[1][0], item[0])):
        incident = owners[vertex]
        incident = incident[incident >= 0]
        faces = refined.faces[incident]
        before = vertices[faces]
        after = before.copy()
        after[faces == vertex] = points[index]
        old_normal = np.cross(before[:, 1] - before[:, 0], before[:, 2] - before[:, 0])
        new_normal = np.cross(after[:, 1] - after[:, 0], after[:, 2] - after[:, 0])
        # 浮点法向检查只筛提案；终态仍必须通过原全量嵌入、面积、排斥及距离门槛。
        if np.any(np.einsum("ij,ij->i", old_normal, new_normal) <= 0):
            rejected += 1
            continue
        vertices[vertex] = points[index]
        accepted.append({"new_vertex": vertex, "reference_probe": index, "reverse_distance_mm": distance})
    record.update(refinement=refinement, selected=accepted, relocated_new_vertices=len(accepted),
                  rejected_orientation_proposals=rejected)
    if not np.array_equal(vertices[:len(mesh.vertices)], mesh.vertices):
        raise ValueError("覆盖细分提案改动了原顶点")
    return trimesh.Trimesh(vertices, refined.faces.copy(), process=False), record


def local_coverage_exclusion(raw, tools, reference, anchor_classifier):
    captured = {}
    def remember(mesh, tool, normals, offsets):
        result = anchor_classifier(mesh, tool, normals, offsets)
        digest = result.get("classification", {}).get("saved_mesh_sha256")
        if digest and digest not in captured:
            captured[digest] = mesh.copy()
        return result

    mesh, record = late_reverse_exclusion(raw, tools, reference, remember)
    record.update(extra_local_coverage_rounds_budget=2, coverage_only_new_midpoints=True)
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
        seed, coverage = coverage_midpoint_seed(working, reference)
        if not coverage["marked_faces"]:
            record["coverage_reason"] = "no_reverse_probe_deficit"
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
