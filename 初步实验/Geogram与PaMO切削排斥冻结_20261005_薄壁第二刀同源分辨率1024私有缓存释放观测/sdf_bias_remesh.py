"""隔离进程中的固定符号场偏移适配，完整后续阶段仍由作者流程执行。"""

import hashlib
import inspect

import pamo
import torch


def install_bias(offset_factor):
    if offset_factor not in (0.0, 0.45, 0.9):
        raise ValueError("只允许已冻结开发对照的偏移幅度")
    digest = hashlib.sha256(open(inspect.getfile(pamo.PaMO), "rb").read()).hexdigest()
    if digest != "0d7781dd3b3bb9579e966dc8ddc016a4b1c0036b8386747511ba092c9591ee7a":
        raise ValueError("实际作者阶段源码摘要改变")

    def remesh(self, tris, tris_min, tris_max, tris_mean):
        # 复用已做原偏移控制核查的计算顺序，仅替换常数；不读回额外阶段网格。
        d = pamo.torchcumesh2sdf.get_sdf(tris, self.R, self.band)
        # 先同步确认独立返回场有效，再释放本进程扩展缓存，降低后续三角化峰值。
        from pathlib import Path
        import json
        torch.cuda.synchronize()
        free_before, total = torch.cuda.mem_get_info()
        pamo.torchcumesh2sdf.free_cached_memory()
        torch.cuda.synchronize()
        free_after, _ = torch.cuda.mem_get_info()
        finite = bool(torch.isfinite(d).all())
        memory = {'resolution': self.R, 'field_shape': list(d.shape), 'field_finite_after_release': finite,
                  'free_bytes_before_release': free_before, 'free_bytes_after_release': free_after,
                  'total_bytes': total, 'scope': '只释放当前进程私有扩展缓存，返回clone场继续参与完整三阶段'}
        (Path(__file__).resolve().parent / 'result/04-SDF私有缓存释放与场存活.json').write_text(json.dumps(memory, ensure_ascii=False, indent=2), 'utf8')
        if not finite:
            raise RuntimeError('缓存释放后的独立场非有限，停止求解')
        d = d - offset_factor / self.R
        v, f = self.vol2mesh(d, return_quads=False)
        v, f = v.cpu().numpy(), f.cpu().numpy()
        v = (((v * self.R + 0.5) / (self.R + 1) * self.margin - self.band) * tris_max + tris_min)
        v = torch.from_numpy(v).float().cuda()
        f = torch.from_numpy(f).int().cuda()
        return v, f

    pamo.PaMO.remesh = remesh
