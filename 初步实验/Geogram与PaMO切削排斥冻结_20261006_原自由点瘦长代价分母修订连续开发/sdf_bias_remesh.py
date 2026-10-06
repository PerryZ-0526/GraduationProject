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
        d = d - offset_factor / self.R
        v, f = self.vol2mesh(d, return_quads=False)
        v, f = v.cpu().numpy(), f.cpu().numpy()
        v = (((v * self.R + 0.5) / (self.R + 1) * self.margin - self.band) * tris_max + tris_min)
        v = torch.from_numpy(v).float().cuda()
        f = torch.from_numpy(f).int().cuda()
        return v, f

    pamo.PaMO.remesh = remesh
