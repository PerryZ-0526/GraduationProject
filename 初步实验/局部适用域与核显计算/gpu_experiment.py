"""核显双精度扫掠微基准；同精度参考、传输与计算分别计时，不冒充端到端系统。"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
from time import perf_counter
import hashlib
import json
import os
import numpy as np

ROOT = Path(__file__).parent


def cpu_sweep(xy, base, tools):
    """与核函数相同的双精度数学定义，使用向量化CPU参考。"""
    result = base.copy()
    for ax, ay, bx, by, radius, z in tools:
        a, d = np.array([ax, ay]), np.array([bx-ax, by-ay])
        length2 = d @ d
        t = np.zeros(len(xy)) if length2 == 0 else np.clip(np.sum((xy-a)*d, axis=1)/length2, 0., 1.)
        squared = np.sum((xy-a-t[:, None]*d)**2, axis=1)
        result = np.where(squared <= radius**2, np.minimum(result, z-np.sqrt(np.maximum(0., radius**2-squared))), result)
    return result


def run():
    # 仅启动OpenCL实验时加载后端，CPU参考允许被CUDA实验独立复用。
    import pyopencl as cl
    if os.environ.get('PYOPENCL_BUILD_OPTIONS', '').strip():
        raise RuntimeError('请清除外部编译选项，避免未记录的精度改变')
    devices = [d for p in cl.get_platforms() for d in p.get_devices(device_type=cl.device_type.GPU)
               if 'Intel' in d.vendor and 'cl_khr_fp64' in d.extensions.split()]
    if len(devices) != 1:
        raise RuntimeError('未找到唯一支持双精度的Intel GPU，不回退CPU冒充GPU')
    device = devices[0]
    ctx = cl.Context([device])
    queue = cl.CommandQueue(ctx, properties=cl.command_queue_properties.PROFILING_ENABLE)
    source = (ROOT/'sweep.cl').read_text(encoding='utf-8')
    started = perf_counter()
    program = cl.Program(ctx, source).build(options=['-cl-std=CL1.2'])
    build_ms = (perf_counter()-started)*1000
    kernel = cl.Kernel(program, 'sweep')
    # 边界、驻点、域外与重复扫掠使用解析期望值，避免仅随机对拍遗漏退化情况。
    special_xy = np.array([[0., 0.], [3., 0.], [3.+1e-8, 0.], [0., 3.-1e-8]], dtype=np.float64)
    special_base = np.full(4, 4., dtype=np.float64)
    special_tools = np.array([[0., 0., 0., 0., 3., 2.5]]*2, dtype=np.float64)
    special_out = np.empty(4, dtype=np.float64)
    special_buffers = [cl.Buffer(ctx, cl.mem_flags.READ_ONLY | cl.mem_flags.COPY_HOST_PTR, hostbuf=a)
                       for a in (special_xy, special_base, special_tools)]
    special_dest = cl.Buffer(ctx, cl.mem_flags.WRITE_ONLY, size=special_out.nbytes)
    kernel(queue, (4,), None, *special_buffers, np.int32(2), special_dest)
    cl.enqueue_copy(queue, special_out, special_dest).wait()
    analytic = np.array([-.5, 2.5, 4., 2.5-np.sqrt(9.-(3.-1e-8)**2)])
    np.testing.assert_allclose(special_out, analytic, atol=1e-10, rtol=0.)
    rng = np.random.default_rng(20260907)
    tools = np.array([[x, .037, x+.25, .037, 3., 2.5] for x in np.linspace(-1, .75, 8)]+
                     [[.037, y, .037, y+.25, 3., 2.5] for y in np.linspace(-1, .75, 8)], dtype=np.float64)
    result = dict(time_bjt=datetime.now(timezone(timedelta(hours=8))).isoformat(), device=device.name,
        driver=device.driver_version, opencl=device.version, pyopencl=cl.VERSION_TEXT,
        build_options=['-cl-std=CL1.2'], build_ms=build_ms, seed=20260907,
        source_sha256=hashlib.sha256(source.encode()).hexdigest(), warmups=3, repeats=10,
        analytic_cases=4, analytic_max_error_mm=float(np.abs(special_out-analytic).max()), runs=[])
    for n in (1000, 10000, 100000):
        xy = rng.uniform(-4., 4., (n, 2)).astype(np.float64)
        base = np.zeros(n, dtype=np.float64)
        output = np.empty_like(base)
        flags = cl.mem_flags
        buffers = [cl.Buffer(ctx, flags.READ_ONLY, size=a.nbytes) for a in (xy, base, tools)]
        dest = cl.Buffer(ctx, flags.WRITE_ONLY, size=output.nbytes)
        timings, errors = [], []
        for iteration in range(-3, 10):
            def reference():
                start = perf_counter()
                reference_value = cpu_sweep(xy, base, tools)
                return reference_value, (perf_counter()-start)*1000
            if iteration % 2 == 0:
                expected, cpu_ms = reference()
            start = perf_counter()
            transfers = [cl.enqueue_copy(queue, buf, a, is_blocking=False) for buf, a in zip(buffers, (xy, base, tools))]
            event = kernel(queue, (n,), None, *buffers, np.int32(len(tools)), dest)
            download = cl.enqueue_copy(queue, output, dest, is_blocking=False)
            download.wait()
            wall_ms = (perf_counter()-start)*1000
            if iteration % 2:
                expected, cpu_ms = reference()
            difference = np.abs(output-expected)
            if not np.isfinite(output).all() or difference.max() > 1e-10:
                raise AssertionError('GPU与CPU数值偏差超限')
            if iteration >= 0:
                timings.append(dict(cpu_ms=cpu_ms, gpu_wall_ms=wall_ms,
                    kernel_ms=(event.profile.end-event.profile.start)*1e-6,
                    transfer_ms=sum(e.profile.end-e.profile.start for e in [*transfers, download])*1e-6))
                errors.append(float(difference.max()))
        result['runs'].append(dict(points=n, tools=len(tools), base='平面零高度，未计原骨面查询',
            max_abs_error_mm=max(errors), timings=timings,
            medians_ms={k:float(np.median([r[k] for r in timings])) for k in timings[0]}))
        print(result['runs'][-1]['medians_ms'], flush=True)
    return result


if __name__ == '__main__':
    out = ROOT/'实验结果'
    out.mkdir(exist_ok=True)
    result = run()
    (out/'gpu.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
