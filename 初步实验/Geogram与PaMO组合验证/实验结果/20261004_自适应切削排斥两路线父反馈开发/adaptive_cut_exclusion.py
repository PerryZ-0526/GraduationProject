"""按整面排斥证据不足触发共边细分，再以独立累计源表面约束修正目标。"""

import numpy as np
import trimesh

from cut_exclusion import face_separators, repair_cut_exclusion_many
from pilot_cut_exclusion import nearest_projection
from exact_alarm_contact import mesh_valid_exact_contacts
from run_constrained_feedback import global_geometry


def refine_faces(mesh, marked):
    """共享边只建一个中点，邻面同步细分；未标记且不邻接细分边的面原样保留。"""
    edges = {tuple(sorted((int(face[i]), int(face[(i + 1) % 3]))))
             for face in mesh.faces[marked] for i in range(3)}
    vertices = mesh.vertices.tolist()
    midpoints = {}
    for edge in sorted(edges):
        midpoints[edge] = len(vertices)
        vertices.append(((mesh.vertices[edge[0]] + mesh.vertices[edge[1]]) / 2).tolist())
    faces, parents = [], []
    for index, original in enumerate(mesh.faces):
        mids = [midpoints.get(tuple(sorted((int(original[i]), int(original[(i + 1) % 3]))))) for i in range(3)]
        count = sum(mid is not None for mid in mids)
        if count == 0:
            replacement = [original.tolist()]
        elif count == 3:
            a, b, c = map(int, original)
            x, y, z = mids
            replacement = [[a, x, z], [x, b, y], [z, y, c], [x, y, z]]
        else:
            # 循环重排保持原绕序，分别处理一个中点或两个相邻边中点。
            start = mids.index(next(mid for mid in mids if mid is not None)) if count == 1 else next(i for i in range(3) if mids[i] is not None and mids[(i + 1) % 3] is not None)
            a, b, c = [int(original[(start + i) % 3]) for i in range(3)]
            x = mids[start]
            if count == 1:
                replacement = [[a, x, c], [x, b, c]]
            else:
                y = mids[(start + 1) % 3]
                replacement = [[x, b, y], [a, x, c], [x, y, c]]
        faces.extend(replacement)
        parents.extend([index] * len(replacement))
    refined = trimesh.Trimesh(np.asarray(vertices), np.asarray(faces), process=False)
    return refined, {"added_vertices": len(vertices) - len(mesh.vertices), "parent_face_ids": parents,
                     "marked_faces": int(np.sum(marked)), "rounding_scope": "中点存储为FP64，细分几何保持需计入坐标舍入"}


def adaptive_exclusion(mesh, tools, cumulative_reference):
    """最多两级细分，参数和预算固定；拒绝不扩大预算，不更换累计参照。"""
    working = mesh.copy()
    record = {"max_levels": 2, "budget_mm": .1, "attempts": [], "accepted": False,
              "scope": "开发第二版；独立累计源约束及整面排斥驱动细分，不提供完整距离或CCD证书"}
    for level in range(3):
        targets = nearest_projection(working, cumulative_reference)
        candidate, details = repair_cut_exclusion_many(working, tools, target_vertices=targets.vertices)
        valid, checks = mesh_valid_exact_contacts(candidate)
        geometry = global_geometry(candidate, cumulative_reference)
        attempt = {"level": level, "exclusion": details, "mesh_valid": valid, "checks": checks, "geometry": geometry,
                   "vertices": len(candidate.vertices), "faces": len(candidate.faces)}
        record["attempts"].append(attempt)
        if details["accepted"] and valid and geometry["probe_max_mm"] <= .1:
            record.update(accepted=True, selected_level=level)
            return candidate, record
        if level == 2:
            break
        marked = np.zeros(len(working.faces), dtype=bool)
        for tool in tools:
            _, raw_slack = face_separators(working, tool)
            _, target_slack = face_separators(targets, tool)
            marked |= (raw_slack < -1e-9) | (target_slack < -1e-9)
        if not marked.any():
            record["reason"] = "no_cut_related_refinement_domain"
            break
        working, refinement = refine_faces(working, marked)
        attempt["refinement"] = refinement
    return mesh.copy(), record
