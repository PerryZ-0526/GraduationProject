"""查询批次驻留CUDA；仅追加工具段，历史变化时从原面重新计算。"""
from collections import OrderedDict
from time import perf_counter
import numpy as np
from cuda_device import CudaDevice, cp


class ResidentDevice(CudaDevice):
    def __init__(self, budget=128*1024*1024):
        super().__init__()
        self.entries, self.budget, self.cache_bytes = OrderedDict(), budget, 0
        self.hits = self.misses = self.reused_pairs = self.computed_pairs = 0

    @property
    def buffer_bytes(self):
        """仅统计仍驻留的显式数组；不把主机键、CUDA上下文或内存池算入本项。"""
        return sum(points.nbytes+values.nbytes for _, points, values, _ in self.entries.values())

    def evaluate(self, xy, base, tools):
        if not len(xy) or not len(tools):
            return base.copy()
        started = perf_counter()
        xy, base, tools = [np.ascontiguousarray(v, dtype=np.float64) for v in (xy, base, tools)]
        key, history = (xy.shape, xy.tobytes(), base.tobytes()), tools.tobytes()
        entry = self.entries.pop(key, None)
        prefix = 0
        a, b, c, d = [cp.cuda.Event() for _ in range(4)]
        a.record()
        if entry is not None:
            old, points, values, size = entry
            self.cache_bytes -= size
            if history.startswith(old):
                prefix = len(old)//48
                self.hits += 1
            else:
                values.set(base)
        else:
            points, values = cp.asarray(xy), cp.asarray(base)
        if prefix == 0:
            self.misses += 1
        remaining = len(tools)-prefix
        # 工具数组很小，仅传新增后缀；同一批点的XY及历史高度留在设备。
        packed = cp.asarray(tools[prefix:])
        b.record()
        if remaining:
            self.kernel(((len(base)+255)//256,), (256,),
                        (points, values, packed, np.int32(remaining), values, np.int32(len(base))))
        c.record()
        result = values.get()
        d.record()
        d.synchronize()
        size = len(key[1])+len(key[2])+len(history)+points.nbytes+values.nbytes
        if size <= self.budget and np.isfinite(result).all():
            while self.cache_bytes+size > self.budget:
                _, removed = self.entries.popitem(last=False)
                self.cache_bytes -= removed[-1]
            self.entries[key] = (history, points, values, size)
            self.cache_bytes += size
        self.reused_pairs += len(base)*prefix
        self.computed_pairs += len(base)*remaining
        self.wall_ms += (perf_counter()-started)*1000
        self.kernel_ms += cp.cuda.get_elapsed_time(b, c)
        self.transfer_ms += cp.cuda.get_elapsed_time(a, b)+cp.cuda.get_elapsed_time(c, d)
        self.calls += 1
        self.points += len(base)
        return result
