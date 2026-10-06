"""原细分排斥失败后，在最佳合法中间对象上执行一次局部逆向目标恢复。"""

from reference_adaptive_exclusion import reference_adaptive_exclusion
from reverse_coverage_targets import restore_reverse_coverage_targets
from cut_exclusion import repair_cut_exclusion_many
from exact_embedding_gate import mesh_valid_full_embedding
from run_constrained_feedback import global_geometry


def late_reverse_exclusion(raw, tools, reference, anchor_classifier):
    captured = {}
    def remember_anchor(mesh, tool, normals, offsets):
        # 只缓存已实际分类对象，原排斥、分类与几何判断照常执行，不改变旧路径。
        result = anchor_classifier(mesh, tool, normals, offsets)
        digest = result.get("classification", {}).get("saved_mesh_sha256")
        if digest and digest not in captured:
            captured[digest] = mesh.copy()
        return result
    mesh, record = reference_adaptive_exclusion(raw, tools, reference, remember_anchor)
    record.update(max_edge_refinement_levels=4, extra_reverse_passes_budget=1, reverse_postprocessing_applied=False)
    if record["accepted"]:
        return mesh, record
    legal = [a for a in record["attempts"] if a["exclusion"]["accepted"] and a["mesh_valid"]]
    if not legal:
        record["late_reverse_reason"] = "no_legal_embedded_intermediate"
        return mesh, record
    best = min(legal, key=lambda attempt: attempt["geometry"]["probe_max_mm"])
    anchors = best["exclusion"]["outside_anchor_certificate"]
    anchor = anchors if isinstance(anchors, dict) else anchors[0]
    original = captured[anchor["classification"]["saved_mesh_sha256"]]
    seed, restoration = restore_reverse_coverage_targets(original, reference, tolerance=.1)
    candidate, details = repair_cut_exclusion_many(seed, tools, target_vertices=seed.vertices,
                                                   anchor_classifier=anchor_classifier)
    valid, checks = False, {}
    if details["accepted"]:
        anchors = details["outside_anchor_certificate"]
        anchor = anchors if isinstance(anchors, dict) else anchors[0]
        valid, checks = mesh_valid_full_embedding(candidate, anchor["classification"])
    geometry = global_geometry(candidate, reference)
    record.update(reverse_postprocessing_applied=True, late_reverse_base_level=best["level"])
    record["attempts"].append({"level": "late_reverse", "coverage_target_relocation": restoration,
        "exclusion": details, "mesh_valid": valid, "checks": checks, "geometry": geometry,
        "vertices": len(candidate.vertices), "faces": len(candidate.faces)})
    record["accepted"] = bool(details["accepted"] and valid and geometry["probe_max_mm"] <= .1)
    if record["accepted"]:
        record["selected_level"] = len(record["attempts"]) - 1
        return candidate, record
    return mesh, record
