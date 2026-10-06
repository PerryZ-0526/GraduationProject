"""隔离FP64归一化与SDF张量入口，保持作者简化、投影及碰撞源。"""

import hashlib
import inspect
from pathlib import Path
import sys
import textwrap
import numpy as np


def install_fp64_sdf_normalization():
    import pamo
    # 新私有扩展仅修复分辨率分解，旧二次幂整场数值已对拍。
    extension = Path('/root/autodl-tmp/graduation_project/constrained_20261005_FP64场分辨率分解修复隔离构建_002c44cedf60/build/cut_sdf_fp64.so')
    if hashlib.sha256(extension.read_bytes()).hexdigest() != 'daed27cf1037c75ab527c6df74a56400ac9cf91c63c184ebd3260d23fec5401e':
        raise ValueError('独立FP64 SDF扩展摘要变化')
    if hashlib.sha256(Path(inspect.getfile(pamo.PaMO)).read_bytes()).hexdigest() != '0d7781dd3b3bb9579e966dc8ddc016a4b1c0036b8386747511ba092c9591ee7a':
        raise ValueError('作者完整阶段源码变化')
    if hashlib.sha256(Path(pamo.torchcumesh2sdf.__file__).read_bytes()).hexdigest() != 'c0836ff8d36fe5c9e2fca8f27e9a341578aa3d716dfb1d0563784710717353ad':
        raise ValueError('作者SDF二进制变化')
    sys.path.insert(0, str(extension.parent))
    import cut_sdf_fp64
    pamo.torchcumesh2sdf = cut_sdf_fp64
    original = pamo.PaMO.preprocess_mesh

    def preprocess(self, points, faces, band, margin):
        # 已安装工具原点的实际CUDA面积保护继续运行，保留作者逆变换参数。
        _, minimum, maximum, mean = original(self, points, faces, band, margin)
        values = np.asarray(points.cpu().numpy(), np.float64)[faces.cpu().numpy()]
        values = ((values - np.asarray(mean, np.float64) - np.asarray(minimum, np.float64)) / float(maximum) + float(band)) / float(margin)
        return np.ascontiguousarray(values, np.float64), minimum, maximum, mean

    pamo.PaMO.preprocess_mesh = preprocess
    run_source = textwrap.dedent(inspect.getsource(pamo.PaMO.run))
    marker = "tris = torch.tensor(tris, dtype=torch.float32, device='cuda:0')"
    if run_source.count(marker) != 1:
        raise ValueError('作者SDF张量入口结构变化')
    # 只改SDF三角张量入口，防止作者run将合法FP64归一化结果再次降精度。
    run_source = run_source.replace(marker, "# 归一化三角数组保留FP64进入独立SDF扩展。\n    tris = torch.tensor(tris, dtype=torch.float64, device='cuda:0')")
    namespace = dict(pamo.PaMO.run.__globals__)
    exec(compile(run_source, '<isolated_FP64_SDF_run>', 'exec'), namespace)
    pamo.PaMO.run = namespace['run']
