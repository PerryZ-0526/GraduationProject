"""原计划全段成员检查与网格提取反证，分别记录而不混称完整骨面重建。"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
from time import perf_counter
import hashlib
import json
import sys
import platform
import numpy as np
import pyvista as pv
from target import cut_field, update_field, box_field
from test_target import membership

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent/'CUDA真实骨面对照'))
from coverage_inputs import original_plan


def quality(mesh):
    faces = mesh.faces.reshape(-1, 4)[:, 1:]
    tri = mesh.points[faces].astype(np.float64)
    lengths = np.linalg.norm(tri-np.roll(tri, 1, axis=1), axis=2)
    area = np.linalg.norm(np.cross(tri[:, 1]-tri[:, 0], tri[:, 2]-tri[:, 0]), axis=1)/2
    q = 4*np.sqrt(3)*area/np.sum(lengths**2, axis=1)
    angles = []
    for i in range(3):
        a, b = tri[:, (i+1)%3]-tri[:, i], tri[:, (i+2)%3]-tri[:, i]
        cosine = np.sum(a*b, axis=1)/(np.linalg.norm(a, axis=1)*np.linalg.norm(b, axis=1))
        angles.append(np.degrees(np.arccos(np.clip(cosine, -1, 1))))
    minimum = np.min(angles, axis=0)
    bad = (~np.isfinite(q)) | (~np.isfinite(minimum)) | (q < .4) | (minimum < 25) | (area <= 1e-12)
    return dict(faces=len(faces), bad_faces=int(bad.sum()), min_q=float(np.nanmin(q)),
                min_angle_deg=float(np.nanmin(minimum)), boundary_edges=mesh.n_open_edges)


def main():
    folder = ROOT/'实验结果'/datetime.now(timezone(timedelta(hours=8))).strftime('%Y%m%d_%H%M%S')
    folder.mkdir(parents=True)
    plan = original_plan()
    points = np.random.default_rng(20260908).uniform([-16, -16, -22], [16, 16, 22], (20000, 3))
    result = dict(time_bj=datetime.now(timezone(timedelta(hours=8))).isoformat(), seed=20260908,
        python=platform.python_version(), machine=platform.machine(), samples=20000,
        plan=plan, plan_sha256=hashlib.sha256(json.dumps(plan, sort_keys=True).encode()).hexdigest(),
        source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in ROOT.glob('*.py')},
        scope='目标工具集合查询；非真实骨面网格全序列', records=[], extraction=[])
    field = np.full(len(points), -np.inf)
    removed = np.zeros(len(points), dtype=bool)
    for item in plan:
        start = perf_counter()
        field = update_field(field, points, item)
        removed |= membership(points, item)
        mismatch = int(np.count_nonzero((field > 0) != removed))
        result['records'].append(dict(step=item['step'], mismatch=mismatch, elapsed_ms=(perf_counter()-start)*1000))
        if mismatch:
            raise RuntimeError('目标集合成员不一致，停止机制实验')
    # 故意不优化提取网格：检查隐式表达是否足以自动满足原质量门槛。
    scenarios = {
        'clipped': [dict(start=[-3, 0, 4], end=[3, 0, 4], radius=2., clip_radius=2.5)],
        'crossing': [dict(start=[-5, 0, 4], end=[5, 0, 4], radius=2., clip_radius=8.),
                     dict(start=[0, -5, 4], end=[0, 5, 4], radius=2., clip_radius=8.)],
        'vertical': [dict(start=[0, 0, 6], end=[0, 0, 1], radius=2., clip_radius=1.5)]}
    for spacing in [.5, .25]:
        grid = pv.ImageData(dimensions=[int(12/spacing)+1]*3, spacing=[spacing]*3, origin=[-6]*3)
        p = grid.points
        for name, tools in scenarios.items():
            values = box_field(p, [4, 4, 4])
            for step, item in enumerate(tools, 1):
                start = perf_counter()
                values = update_field(values, p, item)
                grid.point_data['field'] = values
                mesh = grid.contour([0], scalars='field', method='contour').triangulate()
                row = dict(case=name, spacing_mm=spacing, step=step, **quality(mesh), elapsed_ms=(perf_counter()-start)*1000)
                result['extraction'].append(row)
                mesh.save(folder/f'{name}_{spacing}_{step}.vtp')
    result['status'] = 'completed'
    (folder/'results.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(folder)
    print(json.dumps(result['extraction'], indent=2))


if __name__ == '__main__':
    main()
