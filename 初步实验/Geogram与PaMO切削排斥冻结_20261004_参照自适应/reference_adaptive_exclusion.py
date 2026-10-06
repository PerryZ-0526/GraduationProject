"""参照几何偏差与冻结支撑冲突共同触发局部共边细分的开发候选。"""

import numpy as np
import trimesh

from adaptive_cut_exclusion import refine_faces
from pilot_cut_exclusion import nearest_projection
from cut_exclusion import face_separators, repair_cut_exclusion_many
from exact_alarm_contact import mesh_valid_exact_contacts
from run_constrained_feedback import global_geometry


def reference_adaptive_exclusion(raw, tools, reference, anchor_classifier):
    # 恢复允许超过相对GPU原始输出的旧0.1毫米位移；累计目标验收仍为0.1毫米，显式另冻版本。
    working = nearest_projection(raw, reference)
    record = {"accepted": False, "max_levels": 4, "geometry_mark_threshold_mm": .025,
              "correction_budget_mm_from_each_reference_seed": .1,
              "restoration_raw_displacement_mm": float(np.linalg.norm(working.vertices - raw.vertices, axis=1).max(initial=0)),
              "continuous_target_distance_certified": False, "attempts": []}
    for level in range(5):
        targets = nearest_projection(working, reference)
        candidate, details = repair_cut_exclusion_many(working, tools, target_vertices=targets.vertices,
                                                       anchor_classifier=anchor_classifier)
        valid, checks = mesh_valid_exact_contacts(candidate)
        geometry = global_geometry(candidate, reference)
        attempt = {"level": level, "exclusion": details, "mesh_valid": valid, "checks": checks,
                   "geometry": geometry, "vertices": len(working.vertices), "faces": len(working.faces)}
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
            # 显式拆分不可行顶点的邻面，避免只标记侵入面而保留冲突的宽邻面。
            marked |= np.any(working.faces == details["failed_vertex"], axis=1)
        triangles = targets.triangles
        samples = np.concatenate((triangles.mean(axis=1), (triangles[:, 0] + triangles[:, 1]) / 2,
                                  (triangles[:, 1] + triangles[:, 2]) / 2, (triangles[:, 2] + triangles[:, 0]) / 2))
        # 面心及边中点仅作自适应触发，不能把触发阈值当成整面距离证书。
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
        # 新中点再落到独立参照，不能沿跨凹陷的旧直边持续做几何恒等细分。
        working = nearest_projection(working, reference)
    return raw.copy(), record
