"""新完整父反馈入口：四级原细分后至多一次合法中间对象逆向恢复。"""

from pathlib import Path

import run_reference_cut_feedback as reference
import run_cut_unified_feedback as unified
from late_reverse_exclusion import late_reverse_exclusion
from audit_followup_candidate import sha256
from run_geometry_study import save, now


class LateReverseEngine(reference.ReferenceCutEngine):
    def setup(self):
        info = super().setup()
        info["actual_parameters"].update(extra_reverse_passes_budget=1, reverse_trigger_mm=.1,
            reverse_order="after_original_four_edge_refinements_on_best_legal_embedded_intermediate")
        info["late_reverse_code_sha256"] = {name: sha256(Path(__file__).with_name(name))
            for name in ("late_reverse_exclusion.py", "reverse_coverage_targets.py", "input_full_embedding_audit.py")}
        save(self.output / "03-实际分支协议冻结.json", {"生成时间": now(), "修改时间及修改内容": "首次生成，新实际后处理协议先于候选输出",
            "文档概述": "原候选已通过则不变，失败后最多一次逆向目标提案；全部输出门槛保持",
            "索引目录": ["environment"], "environment": info})
        return info


if __name__ == "__main__":
    reference.reference_adaptive_exclusion = late_reverse_exclusion
    unified.ReferenceCutEngine = LateReverseEngine
    unified.main()
