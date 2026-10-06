"""参照种子原预算无合法输出时，增加一次原GPU顶点目标的局部排斥提案。"""

from quality_ranked_exclusion import quality_ranked_exclusion
from cut_exclusion import repair_cut_exclusion_many
from exact_embedding_gate import mesh_valid_full_embedding
from geometry_error_distribution import geometry_error_distribution
from audit_followup_candidate import quality_distribution


def raw_seed_after_reference_failure(raw, tools, reference, maintenance_source, operand_bits, classifier):
    original_mesh, original = quality_ranked_exclusion(raw, tools, reference, maintenance_source, operand_bits, classifier)
    if original["accepted"]:
        return original_mesh, original
    # 只增加一次原顶点目标提案，未违反约束的顶点不动；不增加GPU或省略材料侧检查。
    mesh, projection = repair_cut_exclusion_many(raw, tools, budget_mm=.1, anchor_classifier=classifier)
    if not projection["accepted"]:
        original["raw_seed_extra_proposal"] = projection
        # 新隔离候选只在原方法失败后自动增加面分离提案，原成功输出不动。
        if raw.euler_number != maintenance_source.euler_number or len(raw.split(only_watertight=False)) != len(maintenance_source.split(only_watertight=False)):
            original["automatic_pair_guard"] = {"accepted": False, "reason": "raw_topology_differs_from_maintenance_source"}
            return original_mesh, original
        from automatic_pair_separation import repair_with_automatic_pair_guard
        guarded, guard = repair_with_automatic_pair_guard(raw, tools, classifier.__self__, budget_mm=.3, max_rounds=3)
        if not guard["accepted"]:
            original["automatic_pair_guard"] = guard
            return original_mesh, original
        return guarded, {"accepted": True, "proposal_role": "automatic_pair_guard_after_failed_raw_seed",
            "raw_seed_projection": guard, "rejected_original_method": original,
            "raw_seed_extra_proposals_budget": 1, "automatic_pair_added_rounds_budget": 3,
            "metrics": guard["metrics"], "same_topology": True,
            "quality": quality_distribution(guarded), "distribution_to_reference": geometry_error_distribution(guarded, reference),
            "fixed_geometry_acceptance_threshold": None, "geometry_quality_decision": "statistics_only_pending_evaluation",
            "continuous_target_distance_certified": False, "movement_CCD_certified": False}
    anchors = projection["outside_anchor_certificate"]
    first = anchors if isinstance(anchors, dict) else anchors[0]
    valid, metrics = mesh_valid_full_embedding(mesh, first["classification"])
    same_topology = mesh.euler_number == maintenance_source.euler_number and len(mesh.split(only_watertight=False)) == len(maintenance_source.split(only_watertight=False))
    record = {"accepted": bool(valid and same_topology),
        "proposal_role": "raw_seed_projection_after_failed_reference_proposals",
        "raw_seed_projection": projection, "rejected_original_method": original,
        "raw_seed_extra_proposals_budget": 1, "metrics": metrics, "same_topology": same_topology,
        "quality": quality_distribution(mesh), "distribution_to_reference": geometry_error_distribution(mesh, reference),
        "fixed_geometry_acceptance_threshold": None, "geometry_quality_decision": "statistics_only_pending_evaluation",
        "continuous_target_distance_certified": False, "movement_CCD_certified": False}
    # 仅补已认证整面排斥且同拓扑输出的数值面积风险，原成功分支保持原返回。
    if not record["accepted"] and same_topology and projection["accepted"] and metrics.get("finite") and metrics.get("full_exact_embedding_bound"):
        from post_exclusion_area_repair import repair_post_exclusion_area
        repaired, area_repair = repair_post_exclusion_area(mesh, tools, classifier.__self__)
        record["post_exclusion_area_repair"] = area_repair
        if area_repair["accepted"]:
            record.update(accepted=True, proposal_role="certified_raw_seed_projection_then_area_repair",
                metrics=area_repair["metrics"], quality=quality_distribution(repaired),
                distribution_to_reference=geometry_error_distribution(repaired, reference))
            return repaired, record
    return mesh, record
