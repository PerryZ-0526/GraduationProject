"""使用作者原有阶段开关，统一从已审计物理源执行简化与安全投影。"""
import hashlib
import inspect
import json
import pamo


def install_exact_source_stage23():
    if hashlib.sha256(open(inspect.getfile(pamo.PaMO), 'rb').read()).hexdigest() != '0d7781dd3b3bb9579e966dc8ddc016a4b1c0036b8386747511ba092c9591ee7a':
        raise ValueError('作者PaMO阶段开关源码改变')
    original = pamo.PaMO.__init__

    def constructor(self, mesh, **kwargs):
        # 本候选每刀统一关闭距离场重建，保留原阶段二与完整碰撞安全投影。
        kwargs['use_stage1'] = False
        kwargs['use_stage3'] = True
        original(self, mesh, **kwargs)
        if self.use_stage1 or not self.use_stage3:
            raise ValueError('作者实际阶段开关与冻结候选不一致')
        print(json.dumps({'configured_stage_calls': {'stage1': 0, 'stage2': 1, 'stage3': 1}, 'input_role': 'audited_physical_boolean_source'}), flush=True)

    pamo.PaMO.__init__ = constructor
