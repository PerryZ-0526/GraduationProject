"""区间过滤代替CPU镜像；不确定输出拒绝，验证模式额外对拍且不计为正式性能。"""
from time import perf_counter
import numpy as np
from cuda_device import CudaDevice, CheckedGpuPatch, ROOT, cp, cpu_sweep
from integrated import Rejected
from local_model import LocalPatch


class IntervalDevice(CudaDevice):
    def __init__(self):
        super().__init__()
        self.kernel = cp.RawKernel((ROOT/'interval_sweep.cu').read_text(encoding='utf-8'), 'sweep',
                                  options=('--std=c++17', '--fmad=false'))
        self.kernel.compile()
        self.last_bounds = None

    def evaluate(self, xy, base, tools):
        # 限制到安全指数范围；极短非零线段不属于本轮区间算子的支持域。
        if any(not np.isfinite(v).all() or np.max(np.abs(v), initial=0.)>1e6 for v in (xy, base, tools)):
            raise Rejected('区间输入非有限或超出1e6毫米数值域')
        if len(tools):
            length = np.linalg.norm(tools[:, 2:4]-tools[:, :2], axis=1)
            if np.any((length>0)&(length<1e-9)) or np.any(tools[:, 4]<=0):
                raise Rejected('区间工具长度或半径超出支持域')
        if not len(xy) or not len(tools):
            self.last_bounds = np.column_stack([base, base])
            return base.copy()
        started = perf_counter()
        xy, base, tools = [np.ascontiguousarray(v, dtype=np.float64) for v in (xy, base, tools)]
        n, m = len(base), len(tools)
        if n>self.capacity:
            self.capacity=n
            self.xy, self.base, self.dest = cp.empty((n,2)), cp.empty(n), cp.empty((n,2))
        if m>self.tool_capacity:
            self.tool_capacity=m
            self.tools=cp.empty((m,6))
        a,b,c,d = [cp.cuda.Event() for _ in range(4)]
        a.record()
        self.xy[:n].set(xy)
        self.base[:n].set(base)
        self.tools[:m].set(tools)
        b.record()
        self.kernel(((n+255)//256,), (256,), (self.xy,self.base,self.tools,np.int32(m),self.dest,np.int32(n)))
        c.record()
        bounds=self.dest[:n].get()
        d.record()
        d.synchronize()
        self.wall_ms+=(perf_counter()-started)*1000
        self.kernel_ms+=cp.cuda.get_elapsed_time(b,c)
        self.transfer_ms+=cp.cuda.get_elapsed_time(a,b)+cp.cuda.get_elapsed_time(c,d)
        self.calls+=1
        self.points+=n
        self.last_bounds=bounds
        return bounds[:,0].copy()

    @property
    def buffer_bytes(self):
        return self.capacity*40+self.tool_capacity*48


class IntervalPatch(CheckedGpuPatch):
    def __init__(self, chart, candidate, device, batch=64, validate=False):
        self.query_batch_faces, self.validate = batch, validate
        self.validation_delta = 0.
        super().__init__(chart, candidate, device)

    def certify(self, vertices, indices, tools, lipschitz):
        bounds, sampled, queries = LocalPatch.certify(self, vertices, indices, tools, lipschitz)
        # 三角不等式补足区间查询误差，最终加法向上取邻点；不沿用CPU实测差值说明。
        return np.nextafter(bounds+self.max_delta, np.inf), sampled, queries

    def height(self, xy, tools):
        started=perf_counter()
        shape=xy.shape[:-1]
        points=np.asarray(xy).reshape(-1,2)
        base_started=perf_counter()
        base=self.chart.height(points)
        self.base_ms+=(perf_counter()-base_started)*1000
        packed=np.array([[*t.start,*t.end,t.radius,t.z] for t in tools],dtype=np.float64).reshape(-1,6)
        value=self.device.evaluate(points,base,packed)
        bounds=self.device.last_bounds
        width=np.nextafter(bounds[:,1]-bounds[:,0],np.inf)
        if not np.isfinite(bounds).all() or np.any(width<0) or np.max(width,initial=0.)>1e-10:
            raise Rejected('区间宽度超过1e-10毫米预算，拒绝发布；不冒充精确CPU回退')
        # 使用区间下端点，整个宽度计入现有证书；不是以实测差值代替数学预算。
        self.max_delta=max(self.max_delta,float(np.max(width,initial=0.)))
        if self.validate:
            reference=cpu_sweep(points,base,packed)
            delta=float(np.max(np.abs(reference-value),initial=0.))
            self.validation_delta=max(self.validation_delta,delta)
            if delta>1e-10:
                raise Rejected('独立验证轮与CPU参照超限')
        self.height_ms+=(perf_counter()-started)*1000
        return value.reshape(shape)

    def update(self, tool):
        try:
            return super().update(tool)
        finally:
            row=self.attempts[-1]
            row['numeric_interval_width_mm']=row.pop('max_gpu_cpu_delta_mm')
            row['validation_max_cpu_delta_mm']=self.validation_delta if self.validate else None
