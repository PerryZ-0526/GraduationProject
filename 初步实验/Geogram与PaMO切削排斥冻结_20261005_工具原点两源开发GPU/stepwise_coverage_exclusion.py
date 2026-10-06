"""双向局部覆盖投影采用有限回退步长，所有实际输出仍通过原完整门槛。"""

from late_reverse_exclusion import late_reverse_exclusion
from bidirectional_coverage_exclusion import bidirectional_midpoint_seed
from cut_exclusion import repair_cut_exclusion_many
from exact_embedding_gate import mesh_valid_full_embedding
from run_constrained_feedback import global_geometry


def stepwise_coverage_exclusion(raw, tools, reference, anchor_classifier):
    captured = {}
    def remember(mesh, tool, normals, offsets):
        result = anchor_classifier(mesh, tool, normals, offsets)
        digest = result.get("classification", {}).get("saved_mesh_sha256")
        if digest and digest not in captured:
            captured[digest] = mesh.copy()
        return result

    mesh, record = late_reverse_exclusion(raw, tools, reference, remember)
    record.update(extra_local_coverage_rounds_budget=2, projection_step_fractions=[1., .5, .25], step_applied_before_orientation_check=True,
                  maximum_coverage_proposals=6, coverage_bidirectional_marking=True,
                  movement_CCD_certified=False)
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
        legal_next = []
        for fraction in (1., .5, .25):
            # 在逐点法向检查之前应用步长，避免完整提案被拒后无法回退该点。
            proposal, current_coverage = bidirectional_midpoint_seed(working, reference, step_fraction=fraction)
            candidate, details = repair_cut_exclusion_many(proposal, tools, target_vertices=proposal.vertices,
                                                           anchor_classifier=remember)
            valid, checks = False, {}
            if details["accepted"]:
                anchors = details["outside_anchor_certificate"]
                anchor = anchors if isinstance(anchors, dict) else anchors[0]
                valid, checks = mesh_valid_full_embedding(candidate, anchor["classification"])
            geometry = global_geometry(candidate, reference)
            record["attempts"].append({"level": "damped_coverage_" + str(round_index), "projection_step_fraction": fraction,
                "coverage_midpoints": current_coverage, "exclusion": details, "mesh_valid": valid, "checks": checks,
                "geometry": geometry, "vertices": len(candidate.vertices), "faces": len(candidate.faces)})
            if details["accepted"] and valid and geometry["probe_max_mm"] <= .1:
                record.update(accepted=True, selected_level=len(record["attempts"]) - 1)
                return candidate, record
            if details["accepted"] and valid:
                legal_next.append((geometry["probe_max_mm"], candidate))
        if not legal_next:
            record["coverage_reason"] = "all_fixed_step_proposals_failed_original_legality_gates"
            break
        working = min(legal_next, key=lambda item: item[0])[1]
    return mesh, record
