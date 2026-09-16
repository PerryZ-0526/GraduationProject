"""CUDA双精度查询后端；复用已有逐查询CPU审计和逐状态验收。"""
from pathlib import Path
from time import perf_counter
import sys
import numpy as np
import cupy as cp

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent/'局部适用域与核显计算'))
from integrated import CheckedGpuPatch, cpu_sweep


class CudaDevice:
    """缓存设备缓冲区，计入上传下载及同步，不静默回退CPU。"""
    def __init__(self):
        if cp.cuda.runtime.getDeviceCount() != 1:
            raise RuntimeError('本次固定实验要求唯一CUDA设备')
        self.kernel = cp.RawKernel((ROOT/'sweep_cuda.cu').read_text(encoding='utf-8'), 'sweep', options=('--std=c++17', '--fmad=false'))
        self.kernel.compile()
        self.capacity = self.tool_capacity = 0
        self.reset()

    def reset(self):
        self.wall_ms = self.kernel_ms = self.transfer_ms = 0.
        self.calls = self.points = 0

    def evaluate(self, xy, base, tools):
        if not len(xy) or not len(tools):
            return base.copy()
        started = perf_counter()
        xy, base, tools = [np.ascontiguousarray(v, dtype=np.float64) for v in (xy, base, tools)]
        n, m = len(base), len(tools)
        if n > self.capacity:
            self.capacity = n
            self.xy, self.base, self.dest = cp.empty((n, 2), dtype=cp.float64), cp.empty(n, dtype=cp.float64), cp.empty(n, dtype=cp.float64)
        if m > self.tool_capacity:
            self.tool_capacity = m
            self.tools = cp.empty((m, 6), dtype=cp.float64)
        a, b, c, d = [cp.cuda.Event() for _ in range(4)]
        a.record()
        self.xy[:n].set(xy)
        self.base[:n].set(base)
        self.tools[:m].set(tools)
        b.record()
        self.kernel(((n+255)//256,), (256,), (self.xy, self.base, self.tools, np.int32(m), self.dest, np.int32(n)))
        c.record()
        result = self.dest[:n].get()
        d.record()
        d.synchronize()
        self.wall_ms += (perf_counter()-started)*1000
        self.kernel_ms += cp.cuda.get_elapsed_time(b, c)
        self.transfer_ms += cp.cuda.get_elapsed_time(a, b)+cp.cuda.get_elapsed_time(c, d)
        self.calls += 1
        self.points += n
        return result
