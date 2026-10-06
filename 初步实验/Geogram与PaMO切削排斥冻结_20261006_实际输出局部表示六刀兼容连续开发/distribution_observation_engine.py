"""将分布排序接入完整GPU入口，几何质量仅作观察，不设置固定达标率。"""

import json
from pathlib import Path
from time import perf_counter

import trimesh
import run_reference_cut_feedback as reference
from run_late_reverse_feedback import LateReverseEngine
from distribution_ranked_exclusion import distribution_ranked_exclusion
from geometry_error_distribution import geometry_error_distribution, cutting_surface_distribution
from audit_followup_candidate import sha256, quality_distribution
from exact_embedding_gate import mesh_valid_full_embedding
from run_geometry_study import now


class DistributionObservationEngine(LateReverseEngine):
    def setup(self):
        info = super().setup()
        info["actual_parameters"].update(geometry_acceptance="observation_only_no_fixed_distance_or_coverage_threshold",
            ranking="worst_area_and_cut_source_P95_then_low_angle_fraction", canonical_source_order=True,
            proposal_generator="unchanged_original_stepwise_fixed_budget")
        info["distribution_code_sha256"] = {name: sha256(Path(__file__).with_name(name)) for name in
            ("distribution_ranked_exclusion.py", "geometry_error_distribution.py", "distribution_observation_engine.py", "canonical_clean_source.py")}
        return info

    def run(self, source, labels, tool, method, folder):
        maintenance = trimesh.load(source, force="mesh", process=False)
        bits = json.loads(Path(labels).read_text("utf8"))["operand_bits"]
        original = reference.reference_adaptive_exclusion
        try:
            # 每次绑定当前刀的真实源与来源，不使用上一刀的分布对象。
            reference.reference_adaptive_exclusion = lambda raw, tools, cumulative, classifier: distribution_ranked_exclusion(
                raw, tools, cumulative, maintenance, bits, classifier)
            return super().run(source, labels, tool, method, folder)
        finally:
            reference.reference_adaptive_exclusion = original


def audit_distribution_observation(source_path, tool_path, labels_path, folder, row):
    if row["execution"]["returncode"]:
        return row
    started = perf_counter()
    source = trimesh.load(source_path, force="mesh", process=False)
    candidate = trimesh.load(Path(folder) / "candidate.obj", force="mesh", process=False)
    valid, metrics = mesh_valid_full_embedding(candidate, row.get("exact_embedding", {}))
    same_topology = candidate.euler_number == source.euler_number and len(candidate.split(only_watertight=False)) == len(source.split(only_watertight=False))
    log = (Path(folder) / "worker.log").read_text("utf8")
    capacity = "exceeds max_blocks" in log or "Number of contacts" in log
    bits = json.loads(Path(labels_path).read_text("utf8"))["operand_bits"]
    geometry = reference.controller.global_geometry(candidate, source)
    passed = valid and same_topology and not capacity and row["cut_exclusion"]["accepted"]
    row.update(output_metrics=metrics, same_topology_as_source=same_topology, geometry_to_maintenance_source=geometry,
               geometry_distribution_to_maintenance_source=geometry_error_distribution(candidate, source),
               cutting_surface_distribution=cutting_surface_distribution(candidate, source, bits),
               quality=quality_distribution(candidate), source_quality=quality_distribution(source), capacity_changed=capacity,
               audited_source_sha256=sha256(source_path), audited_labels_sha256=sha256(labels_path),
               independent_audit_ms=(perf_counter() - started) * 1000, audit_time_beijing=now(),
               geometry_quality_decision="statistics_only_pending_evaluation", continuous_geometry_certified=False,
               status="accepted_geometry_observation" if passed else "legality_audit_rejected")
    return row
