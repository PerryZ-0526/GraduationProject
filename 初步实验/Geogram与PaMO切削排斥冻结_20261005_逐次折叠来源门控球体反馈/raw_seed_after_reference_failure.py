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
        return original_mesh, original
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
    return mesh, record
