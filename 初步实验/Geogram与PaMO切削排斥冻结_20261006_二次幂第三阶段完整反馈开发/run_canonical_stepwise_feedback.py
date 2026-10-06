"""规范布尔源排列的完整父反馈开发，沿用旧逐点覆盖及全部发布门槛。"""

from pathlib import Path

import run_stepwise_coverage_feedback as entry
import run_reference_cut_feedback as reference
from canonical_clean_source import canonical_clean_source
from audit_followup_candidate import sha256


original_cleanup = entry.clean_provenance
original_repair = entry.repair_input


def canonical_cleanup(mesh, bits, **kwargs):
    cleaned, labels, details = original_cleanup(mesh, bits, **kwargs)
    canonical, labels, proof = canonical_clean_source(cleaned, labels)
    # 来源原面号随规范排序同步重排，不能保留错误的旧顺序关联。
    previous = details["surviving_original_face_ids"]
    details["surviving_original_face_ids"] = [previous[index] for index in proof["old_face_ids"]]
    details["canonical_order"] = proof
    return canonical, labels, details


def canonical_repair(mesh, bits, **kwargs):
    repaired, labels, details = original_repair(mesh, bits, **kwargs)
    canonical, labels, proof = canonical_clean_source(repaired, labels)
    details["canonical_order_after_input_repair"] = proof
    return canonical, labels, details


class CanonicalEngine(entry.ReferenceCutEngine):
    def setup(self):
        info = super().setup()
        info["actual_parameters"]["canonical_source_order"] = "exact_coordinate_vertex_sort_and_oriented_face_sort_with_source_labels"
        info["canonical_source_sha256"] = sha256(Path(__file__).with_name("canonical_clean_source.py"))
        info["canonical_feedback_sha256"] = sha256(Path(__file__))
        return info


if __name__ == "__main__":
    entry.clean_provenance = canonical_cleanup
    entry.repair_input = canonical_repair
    entry.ReferenceCutEngine = CanonicalEngine
    reference.reference_adaptive_exclusion = entry.stepwise_coverage_exclusion
    entry.main()
