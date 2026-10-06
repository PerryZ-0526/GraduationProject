"""参照双向覆盖目标匹配与整面排斥开发候选，保留最终几何和嵌入门槛。"""

import numpy as np
import trimesh

from adaptive_cut_exclusion import refine_faces
from pilot_cut_exclusion import nearest_projection
from reverse_coverage_targets import restore_reverse_coverage_targets
from cut_exclusion import face_separators, repair_cut_exclusion_many
from exact_alarm_contact import mesh_valid_exact_contacts
from exact_embedding_gate import mesh_valid_full_embedding
from run_constrained_feedback import global_geometry


def coverage_adaptive_exclusion(raw, tools, reference, anchor_classifier):
    working = nearest_projection(raw, reference)
    record = {"accepted": False, "max_levels": 4, "geometry_mark_threshold_mm": .025,
              "correction_budget_mm_from_each_reference_seed": .1,
              "restoration_raw_displacement_mm": float(np.linalg.norm(working.vertices - raw.vertices, axis=1).max(initial=0)),
              "reverse_target_passes_per_level": 1, "continuous_target_distance_certified": False, "attempts": []}
    for level in range(5):
        # 参照到候选的漏覆盖不会由候选面心探针充分触发；匹配目标后仍需独立完整验收。
        working, coverage = restore_reverse_coverage_targets(working, reference)
        targets = nearest_projection(working, reference)
        candidate, details = repair_cut_exclusion_many(working, tools, target_vertices=targets.vertices,
                                                       anchor_classifier=anchor_classifier)
        if details["accepted"]:
            anchors = details["outside_anchor_certificate"]
            anchor = anchors if isinstance(anchors, dict) else anchors[0]
            valid, checks = mesh_valid_full_embedding(candidate, anchor["classification"])
        else:
            valid, checks = mesh_valid_exact_contacts(candidate)
        geometry = global_geometry(candidate, reference)
        attempt = {"level": level, "coverage_target_relocation": coverage, "exclusion": details,
                   "mesh_valid": valid, "checks": checks, "geometry": geometry,
                   "vertices": len(working.vertices), "faces": len(working.faces)}
        record["attempts"].append(attempt)
        if details["accepted"] and valid and geometry["probe_max_mm"] <= .1:
            record.update(accepted=True, selected_level=level)
            return candidate, record
        if level == 4:
            break
        marked = np.zeros(len(working.faces), dtype=bool)
        for tool in tools:
            _, slack = face_separators(targets, tool)
            marked |= slack < -1e-9
        if "failed_vertex" in details:
            marked |= np.any(working.faces == details["failed_vertex"], axis=1)
        triangles = targets.triangles
        samples = np.concatenate((triangles.mean(axis=1), (triangles[:, 0] + triangles[:, 1]) / 2,
                                  (triangles[:, 1] + triangles[:, 2]) / 2, (triangles[:, 2] + triangles[:, 0]) / 2))
        points = trimesh.Trimesh(samples, np.empty((0, 3), dtype=int), process=False)
        nearest = nearest_projection(points, reference)
        error = np.linalg.norm(samples - nearest.vertices, axis=1).reshape(4, len(working.faces)).max(axis=0)
        marked |= error > .025
        attempt.update(marked_faces=int(marked.sum()), maximum_geometry_trigger_mm=float(error.max(initial=0)))
        if not marked.any():
            record["reason"] = "no_refinement_domain"
            break
        working, refinement = refine_faces(targets, marked)
        attempt["refinement"] = refinement
        working = nearest_projection(working, reference)
    return raw.copy(), record
