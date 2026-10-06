"""物理修复与投影初态编码锚点的完整父反馈，不拼接旧版本结果。"""
from run_physical_geometry_feedback import PhysicalEngine, main
from run_initial_encoding_projection import InitialEncodingEngine
from run_constrained_batch import HERE
from audit_followup_candidate import sha256


class InitialPhysicalEngine(PhysicalEngine, InitialEncodingEngine):
    def setup(self):
        info = super().setup()
        # 同时冻结实际新入口与初态规则，不能仅沿用旧锚点工作器摘要。
        names = ('run_initial_encoding_feedback.py', 'run_initial_encoding_projection.py',
            'encoded_degenerate_anchors.py')
        for name in names:
            (self.output/name).write_bytes((HERE/name).read_bytes())
        info['initial_encoding_feedback_source_sha256'] = {name:sha256(self.output/name) for name in names}
        return info


if __name__ == '__main__':
    main(InitialPhysicalEngine)
