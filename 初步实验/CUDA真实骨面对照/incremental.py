"""有限内存的精确输入前缀复用；不量化、不复用三角网格插值状态。"""
from collections import OrderedDict
from pathlib import Path
import sys
from time import perf_counter
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'局部适用域与核显计算'))
from gpu_experiment import cpu_sweep
from local_model import LocalPatch


class PrefixSweep:
    """缓存由原面和完整工具前缀定义的点值；字节级键避免量化和哈希碰撞误命中。"""
    def __init__(self, evaluate, budget=128*1024*1024):
        self.compute, self.budget = evaluate, budget
        self.entries = OrderedDict()
        self.bytes = self.reused_pairs = self.computed_pairs = self.hits = self.misses = 0

    def evaluate(self, xy, base, tools):
        xy, base, tools = [np.ascontiguousarray(v, dtype=np.float64) for v in (xy, base, tools)]
        key, history = (xy.shape, xy.tobytes(), base.tobytes()), tools.tobytes()
        entry = self.entries.pop(key, None)
        value, prefix = base, 0
        if entry is not None:
            old, cached, size = entry
            self.bytes -= size
            if history.startswith(old):
                value, prefix = cached, len(old)//48
                self.hits += 1
        if prefix == 0:
            self.misses += 1
        self.reused_pairs += len(base)*prefix
        self.computed_pairs += len(base)*(len(tools)-prefix)
        result = self.compute(xy, value, tools[prefix:])
        size = len(key[1])+len(key[2])+len(history)+result.nbytes
        if size <= self.budget and np.isfinite(result).all():
            while self.bytes+size > self.budget:
                _, removed = self.entries.popitem(last=False)
                self.bytes -= removed[2]
            self.entries[key] = (history, result.copy(), size)
            self.bytes += size
        return result


class IncrementalCpuPatch(LocalPatch):
    """CPU享有同样的历史复用，防止将算法减少计算量误计为CUDA收益。"""
    def __init__(self, chart, candidate):
        self.reference_cache = PrefixSweep(cpu_sweep)
        super().__init__(chart, candidate)

    def height(self, xy, tools):
        started = perf_counter()
        shape = xy.shape[:-1]
        points = np.asarray(xy).reshape(-1, 2)
        packed = np.array([[*t.start, *t.end, t.radius, t.z] for t in tools]).reshape(-1, 6)
        value = self.reference_cache.evaluate(points, self.chart.height(points), packed)
        self.height_ms += (perf_counter()-started)*1000
        return value.reshape(shape)
