"""开发级输入面积判定消融，原版PaMO输出和累计几何审计保持原协议。"""

import run_constrained_feedback as controller
from run_adaptive_feedback import AdaptiveEngine, cleanup_and_repair, audit_adaptive
from positive_area_input import positive_area_input
from audit_followup_candidate import sha256
from run_constrained_batch import HERE


class DiagnosticEngine(AdaptiveEngine):
    """记录诊断政策及源码身份，不将输入门控收益归因于新质量算法。"""
    def setup(self):
        info = super().setup()
        info["input_policy"] = "development_true_zero_FP64_and_actual_FP32_input_check_small_positive_area_reported"
        info["output_policy"] = "unchanged_1e_12_area_and_topology_geometry_state_checks"
        info["input_validator_sha256"] = sha256(HERE / "positive_area_input.py")
        info["diagnostic_controller_sha256"] = sha256(HERE / "run_positive_area_feedback.py")
        return info


def main():
    # 只替换状态机的输入/初态/参照校验；输出审计仍使用原来的独立函数。
    controller.RemoteQuality = DiagnosticEngine
    controller.clean_provenance = cleanup_and_repair
    controller.audit_candidate = audit_adaptive
    controller.mesh_valid = positive_area_input
    controller.main()


if __name__ == "__main__":
    main()
