"""完整父反馈入口：双参照停止条件，GPU与既有输入、保存验收保持。"""

import trimesh

import run_stepwise_coverage_feedback as entry
import run_reference_cut_feedback as reference
from run_late_reverse_feedback import LateReverseEngine
from dual_reference_coverage_exclusion import dual_reference_coverage_exclusion
from audit_followup_candidate import sha256
from pathlib import Path


class DualReferenceEngine(LateReverseEngine):
    def setup(self):
        info = super().setup()
        info["actual_parameters"].update(dual_reference_stop_required=True,
            coverage_target="larger_current_probe_error_of_source_and_cumulative_reference",
            maximum_coverage_proposals=6, extra_local_coverage_rounds_budget=2)
        info["dual_reference_coverage_sha256"] = sha256(Path(__file__).with_name("dual_reference_coverage_exclusion.py"))
        return info

    def run(self, source, labels, tool, method, folder):
        maintenance_source = trimesh.load(source, force="mesh", process=False)
        original = reference.reference_adaptive_exclusion
        try:
            # 每刀绑定实际维护源，调用结束恢复模块入口，避免下一刀沿用旧源。
            reference.reference_adaptive_exclusion = lambda raw, tools, cumulative, classifier: dual_reference_coverage_exclusion(
                raw, tools, cumulative, maintenance_source, classifier)
            return super().run(source, labels, tool, method, folder)
        finally:
            reference.reference_adaptive_exclusion = original


if __name__ == "__main__":
    entry.ReferenceCutEngine = DualReferenceEngine
    entry.main()
