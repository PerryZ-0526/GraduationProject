"""局部覆盖恢复同时满足维护源和独立累计参照，沿用固定六次提案预算。"""

from late_reverse_exclusion import late_reverse_exclusion
from bidirectional_coverage_exclusion import bidirectional_midpoint_seed
from cut_exclusion import repair_cut_exclusion_many
from exact_embedding_gate import mesh_valid_full_embedding
from run_constrained_feedback import global_geometry


def dual_reference_geometry(mesh, reference, maintenance_source):
    """分别保留两种距离证据，以较大探针决定候选是否可停止。"""
    cumulative = global_geometry(mesh, reference)
    source = global_geometry(mesh, maintenance_source)
    return {"cumulative": cumulative, "maintenance_source": source,
            "worst_probe_max_mm": max(cumulative["probe_max_mm"], source["probe_max_mm"])}


def dual_reference_coverage_exclusion(raw, tools, reference, maintenance_source, anchor_classifier):
    captured = {}

    def remember(mesh, tool, normals, offsets):
        result = anchor_classifier(mesh, tool, normals, offsets)
        digest = result.get("classification", {}).get("saved_mesh_sha256")
        if digest and digest not in captured:
            captured[digest] = mesh.copy()
        return result

    mesh, record = late_reverse_exclusion(raw, tools, reference, remember)
    record.update(extra_local_coverage_rounds_budget=2, projection_step_fractions=[1., .5, .25],
                  maximum_coverage_proposals=6, step_applied_before_orientation_check=True,
                  dual_reference_stop_required=True, movement_CCD_certified=False)
    if record["accepted"]:
        geometry = dual_reference_geometry(mesh, reference, maintenance_source)
        record["dual_reference_geometry"] = geometry
        if geometry["worst_probe_max_mm"] <= .1:
            return mesh, record
        # 内部累计参照通过仍可能被最终维护源门槛拒绝，不能在这里提前停止。
        record.update(accepted=False, cumulative_only_early_stop_rejected=True)
    legal = []
    for attempt in record["attempts"]:
        if not (attempt["exclusion"]["accepted"] and attempt["mesh_valid"]):
            continue
        anchors = attempt["exclusion"]["outside_anchor_certificate"]
        anchor = anchors if isinstance(anchors, dict) else anchors[0]
        candidate = captured[anchor["classification"]["saved_mesh_sha256"]]
        geometry = dual_reference_geometry(candidate, reference, maintenance_source)
        attempt["dual_reference_geometry"] = geometry
        legal.append((geometry["worst_probe_max_mm"], candidate, geometry))
    if not legal:
        record["coverage_reason"] = "no_legal_embedded_base"
        return mesh, record
    _, working, working_geometry = min(legal, key=lambda item: item[0])
    for round_index in range(2):
        # 每轮仅针对较差的那个参照生成提案，仍分别验收两个参照，不增加提案数量。
        source_worse = (working_geometry["maintenance_source"]["probe_max_mm"] >
                        working_geometry["cumulative"]["probe_max_mm"])
        target = maintenance_source if source_worse else reference
        legal_next = []
        for fraction in (1., .5, .25):
            proposal, coverage = bidirectional_midpoint_seed(working, target, step_fraction=fraction)
            if not coverage["marked_faces"]:
                record["coverage_reason"] = "no_probe_deficit_for_worse_reference"
                break
            candidate, details = repair_cut_exclusion_many(proposal, tools, target_vertices=proposal.vertices,
                                                           anchor_classifier=remember)
            valid, checks = False, {}
            if details["accepted"]:
                anchors = details["outside_anchor_certificate"]
                anchor = anchors if isinstance(anchors, dict) else anchors[0]
                valid, checks = mesh_valid_full_embedding(candidate, anchor["classification"])
            geometry = dual_reference_geometry(candidate, reference, maintenance_source)
            record["attempts"].append({"level": "dual_reference_coverage_" + str(round_index),
                "projection_step_fraction": fraction, "projection_reference": "maintenance_source" if source_worse else "cumulative",
                "coverage_midpoints": coverage, "exclusion": details, "mesh_valid": valid, "checks": checks,
                "geometry": geometry["cumulative"], "dual_reference_geometry": geometry,
                "vertices": len(candidate.vertices), "faces": len(candidate.faces)})
            if details["accepted"] and valid and geometry["worst_probe_max_mm"] <= .1:
                record.update(accepted=True, selected_level=len(record["attempts"]) - 1,
                              dual_reference_geometry=geometry)
                return candidate, record
            if details["accepted"] and valid:
                legal_next.append((geometry["worst_probe_max_mm"], candidate, geometry))
        if not legal_next:
            record["coverage_reason"] = "fixed_step_proposals_failed_original_legality_gates"
            break
        _, working, working_geometry = min(legal_next, key=lambda item: item[0])
    return mesh, record
