"""相同固定XY查询点对拍布尔与局部重建；采样误差不冒充连续误差证书。"""
import json
import numpy as np
import trimesh
from experiment import OUT, load_candidate
from gpu_experiment import cpu_sweep
from real_patch import local_trajectory
from joint import ProjectedSurface


if __name__ == '__main__':
    folder = sorted(OUT.glob('boolean_*'))[-1]
    integrated = sorted(OUT.glob('integrated_*'))[-1]
    candidate, chart = load_candidate()
    rng = np.random.default_rng(20260908)
    radius, theta = 2*np.sqrt(rng.random(10000)), rng.uniform(0, 2*np.pi, 10000)
    xy = np.column_stack([radius*np.cos(theta), radius*np.sin(theta)])
    base = chart.height(xy)
    reference = np.load(integrated/'2_cpu.npz')
    rows = []
    for step in range(1, 17):
        tools = np.array([[*t.start, *t.end, t.radius, t.z] for t in local_trajectory(1.8)[:step]])
        target = cpu_sweep(xy, base, tools)
        for method in ('local', 's2', 's3'):
            if method == 'local':
                mesh = trimesh.Trimesh(reference['snapshots'][step], reference['faces'], process=False)
            else:
                data = np.load(folder/f'{method}_{step}.npz')
                mesh = trimesh.Trimesh(data['vertices'], data['faces'], process=False)
            observed = ProjectedSurface(mesh).query(xy)['z']
            error = np.abs(target-observed)
            assert np.isfinite(error).all()
            rows.append(dict(step=step, method=method, mean_mm=float(error.mean()),
                            p95_mm=float(np.percentile(error, 95)), p99_mm=float(np.percentile(error, 99)),
                            max_mm=float(error.max())))
    (folder/'audit.json').write_text(json.dumps(dict(seed=20260908, points=10000,
        domain='XY中心半径2毫米圆盘均匀面积采样', records=rows), ensure_ascii=False, indent=2), encoding='utf-8')
    print(rows[-3:])
