"""使用作者原有阶段开关，统一从已审计物理源执行简化与安全投影。"""
import hashlib
import inspect
import json
import pamo


def install_exact_source_stage23(use_stage1=False):
    if hashlib.sha256(open(inspect.getfile(pamo.PaMO), 'rb').read()).hexdigest() != '0d7781dd3b3bb9579e966dc8ddc016a4b1c0036b8386747511ba092c9591ee7a':
        raise ValueError('作者PaMO阶段开关源码改变')
    original = pamo.PaMO.__init__

    def constructor(self, mesh, **kwargs):
        # 本刀按已冻结输入准备选择作者原阶段开关，阶段二和完整碰撞投影始终保留。
        kwargs['use_stage1'] = bool(use_stage1)
        kwargs['use_stage3'] = True
        original(self, mesh, **kwargs)
        if self.use_stage1 != bool(use_stage1) or not self.use_stage3:
            raise ValueError('作者实际阶段开关与冻结候选不一致')
        print(json.dumps({'configured_stage_calls': {'stage1': int(use_stage1), 'stage2': 1, 'stage3': 1}, 'input_role': 'audited_physical_boolean_source'}), flush=True)

    pamo.PaMO.__init__ = constructor


def install_minimum_sdf_resolution(resolution=640, use_stage1=False):
    if resolution != 640:
        raise ValueError('冻结恢复分辨率只能是640')
    # 残余正面积小面只启用冻结640原重建；输入实际编码和输出全量审核仍必做。
    install_exact_source_stage23(use_stage1=use_stage1)
    if use_stage1:
        import torch
        original = pamo.PaMO.remesh
        def remesh(self, *args, **kwargs):
            free, total = torch.cuda.mem_get_info()
            print(json.dumps({'stage1_resolution': resolution, 'free_bytes': free, 'total_bytes': total}), flush=True)
            if free < 12 * (1 << 30):
                raise RuntimeError('阶段一恢复可用显存不足12GiB')
            self.R = max(self.R, resolution)
            return original(self, *args, **kwargs)
        pamo.PaMO.remesh = remesh
