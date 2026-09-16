"""将实际原骨面查询后的扫掠移至核显；逐查询CPU审计保护证书数值口径。"""
from time import perf_counter
import os
import numpy as np
from gpu_experiment import ROOT, cpu_sweep
from local_model import LocalPatch, Rejected


class SweepDevice:
    """复用核与缓冲区，分开记录主机墙钟、设备计算及传输。"""
    def __init__(self):
        # OpenCL后端按需加载，复用验收逻辑的CUDA实验不要求安装OpenCL。
        import pyopencl as cl
        if os.environ.get('PYOPENCL_BUILD_OPTIONS', '').strip():
            raise RuntimeError('不允许外部编译选项改变双精度计算')
        devices = [d for p in cl.get_platforms() for d in p.get_devices(device_type=cl.device_type.GPU)
                   if 'Intel' in d.vendor and 'cl_khr_fp64' in d.extensions.split()]
        if len(devices) != 1:
            raise RuntimeError('需要唯一支持双精度的Intel GPU，不静默回退CPU')
        self.device = devices[0]
        self.context = cl.Context(devices)
        self.queue = cl.CommandQueue(self.context, properties=cl.command_queue_properties.PROFILING_ENABLE)
        self.program = cl.Program(self.context, (ROOT/'sweep.cl').read_text(encoding='utf-8')).build(['-cl-std=CL1.2'])
        self.kernel = cl.Kernel(self.program, 'sweep')
        self.capacity = self.tool_capacity = 0
        self.reset()

    def reset(self):
        """每步清零统计，不清空已分配设备内存。"""
        self.wall_ms = self.kernel_ms = self.transfer_ms = 0.
        self.calls = self.points = 0

    def evaluate(self, xy, base, tools):
        # 此方法仅属于OpenCL设备，不影响使用同一检查模型的其他后端。
        import pyopencl as cl
        if not len(xy) or not len(tools):
            return base.copy()
        started = perf_counter()
        xy, base, tools = [np.ascontiguousarray(a, dtype=np.float64) for a in (xy, base, tools)]
        if len(xy) > self.capacity:
            self.capacity = len(xy)
            self.buffers = [cl.Buffer(self.context, cl.mem_flags.READ_WRITE, size=size)
                            for size in (xy.nbytes, base.nbytes, base.nbytes)]
        if len(tools) > self.tool_capacity:
            self.tool_capacity = len(tools)
            self.tools_buffer = cl.Buffer(self.context, cl.mem_flags.READ_ONLY, size=tools.nbytes)
        a, b, dest = self.buffers
        events = [cl.enqueue_copy(self.queue, buf, value, is_blocking=False)
                  for buf, value in [(a, xy), (b, base), (self.tools_buffer, tools)]]
        event = self.kernel(self.queue, (len(xy),), None, a, b, self.tools_buffer, np.int32(len(tools)), dest)
        output = np.empty_like(base)
        download = cl.enqueue_copy(self.queue, output, dest, is_blocking=False)
        download.wait()
        self.wall_ms += (perf_counter()-started)*1000
        self.kernel_ms += (event.profile.end-event.profile.start)*1e-6
        self.transfer_ms += sum(e.profile.end-e.profile.start for e in [*events, download])*1e-6
        self.calls += 1
        self.points += len(xy)
        return output


class CheckedGpuPatch(LocalPatch):
    """GPU参与重建及证书高度查询，CPU逐查询数值审计包含在正式计时中。"""
    def __init__(self, chart, candidate, device, reference=cpu_sweep):
        self.device = device
        # 默认仍完整CPU审计；可注入与完整历史等价的增量CPU参照，不允许省略逐点比较。
        self.reference = reference
        super().__init__(chart, candidate)

    def height(self, xy, tools):
        started = perf_counter()
        shape = xy.shape[:-1]
        points = np.asarray(xy).reshape(-1, 2)
        base_started = perf_counter()
        base = self.chart.height(points)
        self.base_ms += (perf_counter()-base_started)*1000
        packed = np.array([[*t.start, *t.end, t.radius, t.z] for t in tools], dtype=np.float64).reshape(-1, 6)
        value = self.device.evaluate(points, base, packed)
        check_started = perf_counter()
        reference = self.reference(points, base, packed)
        delta = float(np.max(np.abs(value-reference), initial=0.))
        self.reference_ms += (perf_counter()-check_started)*1000
        if not np.isfinite(value).all() or delta > 1e-10:
            raise Rejected('GPU逐查询CPU对拍超限，拒绝本步')
        self.max_delta = max(self.max_delta, delta)
        self.height_ms += (perf_counter()-started)*1000
        return value.reshape(shape)

    def certify(self, vertices, indices, tools, lipschitz):
        bounds, sampled, queries = super().certify(vertices, indices, tools, lipschitz)
        # 每个格点已与CPU对拍；三角不等式补足本步实测数值差，不放宽0.1毫米门槛。
        return bounds+self.max_delta, sampled, queries

    def update(self, tool):
        self.device.reset()
        self.base_ms = self.reference_ms = self.max_delta = 0.
        try:
            return super().update(tool)
        finally:
            self.attempts[-1].update(gpu_wall_ms=self.device.wall_ms, gpu_kernel_ms=self.device.kernel_ms,
                gpu_transfer_ms=self.device.transfer_ms, gpu_calls=self.device.calls,
                gpu_points=self.device.points, base_ms=self.base_ms, reference_ms=self.reference_ms,
                # 驻留后端报告全部缓存设备数组；旧后端保持原缓冲区口径，不含CUDA上下文和内存池。
                max_gpu_cpu_delta_mm=self.max_delta, device_buffer_bytes=getattr(self.device, 'buffer_bytes', self.device.capacity*32+self.device.tool_capacity*48))
