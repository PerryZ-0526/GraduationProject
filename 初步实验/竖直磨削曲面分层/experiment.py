"""固定参数逐状态分层生成与解析几何诊断；强基线未运行时不作优势结论。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from time import perf_counter
import hashlib
import json
import sys
import numpy as np
import pyvista as pv
import trimesh
from axis_patch import generate, residual, exact_distance

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'CUDA真实骨面对照'))
from coverage_inputs import original_plan


def quality(mesh):
    tri = mesh.triangles
    edges = np.roll(tri, -1, axis=1)-tri
    lengths = np.linalg.norm(edges, axis=2)
    area = np.linalg.norm(np.cross(edges[:, 0], -edges[:, 2]), axis=1)/2
    q = 4*np.sqrt(3)*area/np.sum(lengths**2, axis=1)
    angles = []
    for i in range(3):
        a, b = -edges[:, (i-1) % 3], edges[:, i]
        angles.append(np.degrees(np.arccos(np.clip(np.sum(a*b, axis=1)/(np.linalg.norm(a, axis=1)*np.linalg.norm(b, axis=1)), -1, 1))))
    minimum = np.min(angles, axis=0)
    bad = (minimum < 25) | (q < .4) | (area <= 1e-12) | ~np.isfinite(q)
    return dict(vertices=len(mesh.vertices), faces=len(mesh.faces), min_angle_deg=float(minimum.min()),
                min_q=float(q.min()), bad_faces=int(bad.sum()), shape_pass=bool(not bad.any()))


def main():
    now = datetime.now(ZoneInfo('Asia/Shanghai'))
    out = HERE / '实验结果' / now.strftime('%Y%m%d_%H%M%S')
    out.mkdir(parents=True)
    plan = original_plan()
    classification = []
    for item in plan:
        a, b = np.array(item['start']), np.array(item['end'])
        motion = 'horizontal' if a[2] == b[2] else ('vertical' if np.array_equal(a[:2], b[:2]) else 'oblique')
        clipping = max(np.linalg.norm(a[:2]), np.linalg.norm(b[:2]))+item['radius'] > item['clip_radius']
        classification.append(dict(item, motion=motion, needs_radial_clip=bool(clipping)))
    rows, series = [], {}
    for h, preserve in [(h, p) for h in (.4, .25) for p in (True, False)]:
        method = 'all_seams' if preserve else 'sharp_only'
        for step, z in enumerate((1.8, 1., .25, 0., -.0001, -.05, -.25, -1., -2.), 1):
            started = perf_counter()
            mesh, labels, seams = generate(z, spacing=h, preserve_tangent_seam=preserve)
            metrics = quality(mesh)
            # 顶点、边中点及重心仅作解析残差诊断；零残差不等同双向误差合格。
            probes = np.concatenate([mesh.triangles, (mesh.triangles+np.roll(mesh.triangles, -1, axis=1))/2,
                                     mesh.triangles.mean(axis=1)[:, None, :]], axis=1)
            errors = exact_distance(probes, z)
            # 目标到网格按曲面分层采样；只报告抽样距离，不包装成严格Hausdorff证书。
            rng = np.random.default_rng(20260909)
            phi = rng.uniform(0., 2*np.pi, 1024)
            theta_max = np.arccos(max(0., z)/2.)
            theta = np.arccos(rng.uniform(np.cos(theta_max), 1., 1024))
            rr = 2*np.sin(theta)
            truth = [np.column_stack([rr*np.cos(phi), rr*np.sin(phi), z-2*np.cos(theta)])]
            rr = np.sqrt(rng.uniform((2*np.sin(theta_max))**2, 16., 1024))
            truth.append(np.column_stack([rr*np.cos(phi), rr*np.sin(phi), np.zeros(1024)]))
            if z < 0:
                truth.append(np.column_stack([2*np.cos(phi), 2*np.sin(phi), rng.uniform(z, 0., 1024)]))
            _, reverse, _ = trimesh.proximity.closest_point(mesh, np.vstack(truth))
            forward = exact_distance(probes.reshape(-1, 3), z)
            distances = dict(mesh_to_target=[float(np.mean(forward)), *map(float, np.percentile(forward, [95, 99])), float(np.max(forward))],
                target_to_mesh=[float(np.mean(reverse)), *map(float, np.percentile(reverse, [95, 99])), float(np.max(reverse))])
            row = dict(step=step, center_z=z, spacing_mm=h, method=method, **metrics,
                sampled_distances_mean_p95_p99_max_mm=distances,
                diagnostic_surface_residual_mm=float(errors.max()), winding=bool(mesh.is_winding_consistent),
                euler=mesh.euler_number, seam_count=len(seams), total_ms=(perf_counter()-started)*1000,
                accepted=False, reason='只有局部开放面形状/共边和残差诊断，未完成双向误差及整骨验收')
            rows.append(row)
            filename = f'{method}_h{h}_step{step}.vtp'
            poly = pv.PolyData(mesh.vertices, np.column_stack([np.full(len(mesh.faces), 3), mesh.faces]).ravel())
            poly.cell_data['surface'] = np.array([{'sphere':0, 'cylinder':1, 'plane':2, 'mixed':3}[x] for x in labels])
            poly.save(out / filename)
            series.setdefault(f'竖直磨削分层 / {method} / h={h} / 解析开放面', []).append(dict(row, mesh=filename,
                error_bound_mm=None, status='解析机制候选：不是合格整骨发布'))
            print(method, h, z, metrics['min_angle_deg'], metrics['bad_faces'], flush=True)
    data = dict(time_beijing=now.strftime('%Y-%m-%d %H:%M:%S'), seed=20260909, target_samples_per_stratum=1024, plan=classification,
                plan_sha256=hashlib.sha256(json.dumps(plan, sort_keys=True).encode()).hexdigest(), rows=rows,
                source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in HERE.glob('*.py')},
                strong_baseline_status='远端SSH不可达，本轮未执行Geogram/RXMesh对照；不作优势结论')
    (out / 'results.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    (out / 'viewer.json').write_text(json.dumps(dict(viewer_schema=1, series=series), ensure_ascii=False, indent=2), encoding='utf-8')
    print(out)


if __name__ == '__main__':
    main()
