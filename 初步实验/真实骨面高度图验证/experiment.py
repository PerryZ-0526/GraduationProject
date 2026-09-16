"""真实骨面投影域、原面叠置误差和局部浅磨削验证；不运行完整138步计划。"""
import hashlib
import json
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from time import perf_counter
from collections import Counter
import numpy as np
import pymeshlab as pm
from projection import load_bone, ProjectedSurface, R
from surface_patch import verify_chart
from real_patch import BoneChart, RealPatch, local_trajectory, Rejected

BASE = Path(__file__).parent
OUT = BASE/'实验结果'


def statistics(values):
    values = np.asarray(values)
    values = values[np.isfinite(values)]
    return dict(mean=float(values.mean()), p95=float(np.percentile(values, 95)),
                p99=float(np.percentile(values, 99)), min=float(values.min()), max=float(values.max()))


def independent_audit(surface, model):
    """全骨射线求原面，再用独立线段距离公式校验随机面内点。"""
    rng = np.random.default_rng(20260907)
    ids = rng.integers(len(model.faces), size=10000)
    uv = rng.random((len(ids), 2))
    uv[uv.sum(axis=1) > 1] = 1-uv[uv.sum(axis=1) > 1]
    weights = np.column_stack((uv, 1-uv.sum(axis=1)))
    points = np.einsum('fi,fij->fj', weights, model.vertices[model.faces[ids]])
    raw = surface.query(points[:, :2])
    target = raw['z'].copy()
    for tool in model.tools:
        start, end = np.asarray(tool.start), np.asarray(tool.end)
        delta = end-start
        projection = np.clip(np.sum((points[:, :2]-start)*delta, axis=1)/np.sum(delta**2), 0., 1.)
        squared = np.sum((points[:, :2]-start-projection[:, None]*delta)**2, axis=1)
        inside = squared < tool.radius**2
        target[inside] = np.minimum(target[inside], tool.z-np.sqrt(tool.radius**2-squared[inside]))
    error = np.abs(target-points[:, 2])
    assert np.all(np.isfinite(error)) and np.all(error <= model.bounds[ids]+1e-10)
    check = pm.MeshSet()
    check.add_mesh(pm.Mesh(model.vertices, model.faces))
    check.compute_selection_by_self_intersections_per_face()
    return dict(vertical_error_mm=statistics(error), over_01mm=int(np.sum(error > .1)),
                self_intersection_faces=check.current_mesh().selected_face_number(), samples=10000,
                remaining_to_next_surface_mm=statistics(target-raw['z']+raw['top_interval_mm']))


def main():
    OUT.mkdir(exist_ok=True)
    started = perf_counter()
    original, local, transform = load_bone()
    surface = ProjectedSurface(local)
    preparation_ms = (perf_counter()-started)*1000
    surveys = []
    for spacing in (.3, .15):
        for radius in (4., 9., 12.5, 15.):
            axis = np.arange(-radius+.031, radius, spacing)
            points = np.array(np.meshgrid(axis, axis)).reshape(2, -1).T
            points = points[np.linalg.norm(points, axis=1) < radius]
            result = surface.query(points)
            valid = result['face'] >= 0
            normals = local.face_normals[result['face'][valid], 2]
            slopes = np.sqrt(np.maximum(0., 1-normals**2))/np.abs(normals)
            surveys.append(dict(radius_mm=radius, spacing_mm=spacing, samples=len(points),
                                missing=int(np.sum(~valid)), multiple_front=int(np.sum(result['front_layers'] > 1)),
                                top_height_mm=statistics(result['z']), slope=statistics(slopes),
                                top_interval_mm=statistics(result['top_interval_mm'])))
            if radius == 15 and spacing == .15:
                np.savez_compressed(OUT/'projection_map.npz', xy=points, **result)
            print('SURVEY', radius, spacing, int(np.sum(~valid)), flush=True)
    charts, selected_polygons = [], None
    for half_width in (4., 6., 8., 10.):
        audit, polygons = verify_chart(surface, half_width)
        charts.append(audit)
        if half_width == 6 and audit['accepted']:
            selected_polygons = polygons
        print('CHART', half_width, audit['accepted'], flush=True)
    if selected_polygons is None:
        raise RuntimeError('预定12×12 mm区域未通过，不执行后续高度图磨削')
    chart = BoneChart(surface, selected_polygons)
    runs = []
    for spacing, center_z, half_width in ((.4, 2.95, 4.), (.25, 2.95, 4.), (.16, 2.95, 4.),
                                          (.25, 2.5, 4.), (.25, 1.8, 4.), (.25, 1.8, 5.), (.16, 1.8, 5.)):
        start = perf_counter()
        model = RealPatch(chart, spacing, half_width)
        initial = model.vertices.copy()
        initialization_ms = (perf_counter()-start)*1000
        initial_audit = dict(min_q=float(model.q.min()), min_angle_deg=float(model.angles.min()),
                             overlay_max_mm=float(model.bounds.max()))
        for tool in local_trajectory(center_z):
            previous = model.vertices[:, 2].copy()
            try:
                row = model.update(tool)
                row['changed_vertices'] = int(np.sum(np.abs(model.vertices[:, 2]-previous) > 1e-10))
            except Rejected:
                break
        audit = independent_audit(surface, model)
        assert np.array_equal(initial[model.boundary], model.vertices[model.boundary])
        runs.append(dict(spacing_mm=spacing, center_z_mm=center_z, half_width_mm=half_width,
                         initialization_ms=initialization_ms, initial=initial_audit,
                         requested_steps=16, accepted_steps=len(model.tools), faces=len(model.faces),
                         changed_steps=sum(a.get('changed_vertices', 0) > 0 for a in model.attempts),
                         max_vertex_removal_mm=float((initial[:, 2]-model.vertices[:, 2]).max()),
                         boundary_unchanged=True, attempts=model.attempts, independent=audit))
        np.savez_compressed(OUT/f'local_mesh_{spacing}_z{center_z}_w{half_width}.npz', initial=initial, vertices=model.vertices,
                            faces=model.faces, transform=transform, bounds=model.bounds, q=model.q)
        print('LOCAL', spacing, len(model.tools), runs[-1]['changed_steps'], audit, flush=True)
    data = dict(time_beijing=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),
                source=str(Path(R.SCAP_STL)), source_sha256=hashlib.sha256(Path(R.SCAP_STL).read_bytes()).hexdigest(),
                source_faces=len(local.faces), source_watertight=bool(local.is_watertight),
                transform=transform.tolist(), preparation_ms=preparation_ms,
                chart_lipschitz=chart.lipschitz, chart_ceiling_mm=chart.ceiling,
                shared_solver_sha256=hashlib.sha256((BASE.parent/'局部区域重建阶段一'/'patch_model.py').read_bytes()).hexdigest(),
                surveys=surveys, charts=charts, runs=runs, seed=20260907,
                original_plan_phases=dict(Counter(item[0] for item in R.trajectory())),
                code_sha256={name: hashlib.sha256((BASE/name).read_bytes()).hexdigest() for name in
                             ['projection.py', 'surface_patch.py', 'real_patch.py', 'experiment.py']})
    text = json.dumps(data, ensure_ascii=False, indent=2)
    (OUT/'results.json').write_text(text, encoding='utf8')
    stamp = datetime.now(ZoneInfo('Asia/Shanghai')).strftime('%Y%m%d_%H%M%S')
    (OUT/f'run_{stamp}.json').write_text(text, encoding='utf8')


if __name__ == '__main__':
    main()
