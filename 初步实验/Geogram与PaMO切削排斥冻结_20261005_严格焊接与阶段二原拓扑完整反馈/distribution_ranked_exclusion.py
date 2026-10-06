"""在原有限提案的合法对象中按误差分布选取，不设置固定几何达标率。"""

from stepwise_coverage_exclusion import stepwise_coverage_exclusion
from dual_reference_coverage_exclusion import dual_reference_geometry
from geometry_error_distribution import geometry_error_distribution, cutting_surface_distribution
from audit_followup_candidate import quality_distribution


def distribution_ranked_exclusion(raw, tools, reference, maintenance_source, operand_bits, classifier):
    captured = {}

    def remember(mesh, tool, normals, offsets):
        result = classifier(mesh, tool, normals, offsets)
        digest = result.get("classification", {}).get("saved_mesh_sha256")
        if digest:
            captured[digest] = mesh.copy()
        return result

    original_mesh, original = stepwise_coverage_exclusion(raw, tools, reference, remember)
    rows, candidates = [], []
    seen = set()
    for index, attempt in enumerate(original["attempts"]):
        if not attempt["mesh_valid"] or not attempt["exclusion"]["accepted"]:
            continue
        anchors = attempt["exclusion"]["outside_anchor_certificate"]
        anchor = anchors if isinstance(anchors, dict) else anchors[0]
        digest = anchor["classification"]["saved_mesh_sha256"]
        if digest in seen:
            continue
        seen.add(digest)
        mesh = captured[digest]
        distributions = {"maintenance_source": geometry_error_distribution(mesh, maintenance_source),
                         "cumulative_reference": geometry_error_distribution(mesh, reference)}
        local = cutting_surface_distribution(mesh, maintenance_source, operand_bits)
        quantiles = [value[direction]["quantiles_mm"]["0.95"] for value in distributions.values()
                     for direction in ("area_forward", "area_reverse")]
        if local["status"] == "measured":
            quantiles.append(local["distribution"]["quantiles_mm"]["0.95"])
        quality = quality_distribution(mesh)
        # P95仅用作有限候选的排序目标，不是误差或达标比例拒绝门槛。
        score = (max(quantiles), quality["angle_below_10_deg"]["fraction"])
        row = {"original_attempt_index": index, "saved_sha256": digest, "geometry_distribution": distributions,
               "cutting_surface": local, "quality": quality, "ranking_score": list(score)}
        rows.append(row)
        candidates.append((score, mesh, index))
    record = {"accepted": bool(candidates), "acceptance_scope": "legality_for_geometry_observation_only",
              "fixed_geometry_acceptance_threshold": None, "proposal_generator": original,
              "distribution_candidates": rows, "ranking": "min_worst_P95_then_low_angle_face_fraction",
              "continuous_target_distance_certified": False, "movement_CCD_certified": False}
    if not candidates:
        record["reason"] = "no_legal_embedded_candidate_in_original_fixed_budget"
        return original_mesh, record
    _, selected, index = min(candidates, key=lambda item: item[0])
    record.update(selected_original_attempt_index=index,
                  geometry=dual_reference_geometry(selected, reference, maintenance_source),
                  geometry_quality_decision="statistics_only_pending_evaluation")
    return selected, record
