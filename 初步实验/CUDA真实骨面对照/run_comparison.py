"""真实骨面受限16步：CPU/CUDA逐状态管线与Geogram布尔诊断。"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
from time import perf_counter
import hashlib
import json
import argparse
import shutil
import subprocess
import numpy as np
import trimesh
import pymeshlab
from cuda_device import CudaDevice, CheckedGpuPatch, cpu_sweep, cp
from experiment import load_candidate
from local_model import LocalPatch
from dynamic import run_sequence
from real_patch import local_trajectory
from joint import mesh_quality, ProjectedSurface
from stitch import topology

ROOT = Path(__file__).resolve().parent


def stats(values):
    values = np.asarray(values)
    if not len(values):
        return None
    return dict(mean=float(values.mean()), p95=float(np.percentile(values, 95)),
                p99=float(np.percentile(values, 99)), max=float(values.max()), min=float(values.min()))


def face_keys(mesh):
    """按原始双精度坐标构造无序三角形键，不以粗量化掩盖几何变化。"""
    return [tuple(sorted(map(tuple, tri))) for tri in mesh.triangles]


def export_double(mesh):
    """使用17位有效数字而非17位小数，避免接近零坐标在Python端先损失精度。"""
    vertices = ['v '+' '.join(format(float(x), '.17g') for x in p) for p in mesh.vertices]
    faces = ['f '+' '.join(str(int(i)+1) for i in f) for f in mesh.faces]
    return '\n'.join(vertices+faces)+'\n'


def quality(mesh, original_keys):
    """全体变化面均检查；同时给出公共ROI和原有差面统计。"""
    changed = np.array([key not in original_keys for key in face_keys(mesh)])
    tri = mesh.triangles
    roi = np.all(tri.max(axis=1) >= [-4., -4., -2.], axis=1) & np.all(tri.min(axis=1) <= [4., 4., 3.], axis=1)
    report = dict(faces=len(mesh.faces), changed_faces=int(changed.sum()), **topology(mesh))
    for name, ids in [('whole', np.ones(len(mesh.faces), dtype=bool)), ('changed', changed), ('roi', roi)]:
        q, angle, area = mesh_quality(mesh.vertices, mesh.faces[ids])
        invalid = ~np.isfinite(q) | ~np.isfinite(angle)
        # 退化导致的无定义内角按质量下界0记录，同时显式计数，避免输出NaN掩盖失败。
        report[name] = dict(faces=int(ids.sum()), min_q=float(np.nan_to_num(q, nan=0).min()) if len(q) else None,
            min_angle_deg=float(np.nan_to_num(angle, nan=0).min()) if len(angle) else None,
            invalid_angle_or_q=int(invalid.sum()), degenerate=int(np.sum(area <= 1e-12)),
            bad_faces=int(np.sum((q < .4) | (angle < 25) | (area <= 1e-12) | invalid)))
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--reuse-local', type=Path)
    args = parser.parse_args()
    folder = ROOT/'实验结果'/datetime.now(timezone(timedelta(hours=8))).strftime('%Y%m%d_%H%M%S')
    folder.mkdir(parents=True)
    result = dict(time_bjt=folder.name, status='running', seed=20260908, runs=[], audits=[], errors=[])
    def save():
        (folder/'results.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    save()
    try:
        candidate, chart = load_candidate()
        original_keys = set(face_keys(candidate['whole']))
        result['initial'] = quality(candidate['whole'], original_keys)
        result['trajectory'] = [t.__dict__ for t in local_trajectory(1.8)]
        device = None
        if args.reuse_local:
            # 仅重跑I/O修正后的Geogram；既有CPU/CUDA计时不伪装为新测量。
            previous_result = json.loads((args.reuse_local/'results.json').read_text(encoding='utf-8'))
            result['reused_local_run'] = str(args.reuse_local)
            result['runs'] = [r for r in previous_result['runs'] if r['method'] in ('cpu','cuda_checked')]
            result['state_deltas'] = previous_result['state_deltas']
            result['cuda_setup_warmup_ms'] = previous_result['cuda_setup_warmup_ms']
            for path in args.reuse_local.glob('*_cpu.npz'):
                shutil.copy2(path, folder/path.name)
            for path in args.reuse_local.glob('*_cuda_checked.npz'):
                shutil.copy2(path, folder/path.name)
        else:
            started = perf_counter()
            device = CudaDevice()
            device.evaluate(np.zeros((1000, 2)), np.zeros(1000), np.array([[0., 0., .25, 0., 3., 1.8]]))
            result['cuda_setup_warmup_ms'] = (perf_counter()-started)*1000
        result['cupy_version'] = cp.__version__
        save()
        # 顺序交替方法顺序，避免同时占用GPU；每轮全部16步，失败保留记录。
        for repeat in range(0 if args.reuse_local else 3):
            states = {}
            for method in (['cpu', 'cuda_checked'] if repeat%2 == 0 else ['cuda_checked', 'cpu']):
                factory = LocalPatch if method == 'cpu' else lambda c, v: CheckedGpuPatch(c, v, device)
                started = perf_counter()
                model, records = run_sequence(candidate, chart, 1.8, model_factory=factory)
                result['runs'].append(dict(repeat=repeat, method=method, sequence_with_setup_ms=(perf_counter()-started)*1000, records=records))
                states[method] = np.asarray(model.snapshots)
                np.savez_compressed(folder/f'{repeat}_{method}.npz', snapshots=states[method], faces=model.faces, bounds=model.bounds)
                save()
            equal = states['cpu'].shape == states['cuda_checked'].shape
            delta = float(np.abs(states['cpu']-states['cuda_checked']).max()) if equal else None
            result.setdefault('state_deltas', []).append(dict(repeat=repeat, same_shape=equal, max_delta_mm=delta))
            save()
            if not equal or delta > 1e-10:
                raise RuntimeError('CPU/CUDA状态不一致，停止比较并保留失败证据')
        # 共享独立原骨面射线查询位置；目标高度公式与当前方法一致，不是独立全域证明。
        rng = np.random.default_rng(20260908)
        r, theta = 2*np.sqrt(rng.random(2048)), rng.uniform(0, 2*np.pi, 2048)
        xy = np.column_stack([r*np.cos(theta), r*np.sin(theta)])
        base = chart.surface.query(xy)['z']
        np.savez_compressed(folder/'audit_points.npz', xy=xy, base=base)
        targets = [cpu_sweep(xy, base, np.array([[*t.start, *t.end, t.radius, t.z] for t in local_trajectory(1.8)[:step]])) for step in range(1, 17)]
        def audit(mesh, method, step):
            observed = ProjectedSurface(mesh).query(xy)['z']
            valid = np.isfinite(observed) & np.isfinite(targets[step-1])
            row = dict(method=method, step=step, missing=int((~valid).sum()), sampled_vertical_error_mm=stats(np.abs(observed[valid]-targets[step-1][valid])))
            result['audits'].append(row)
        local = np.load(folder/'2_cpu.npz')
        for step in range(1, len(local['snapshots'])):
            whole = candidate['whole'].copy()
            whole.vertices[candidate['mapping']] = local['snapshots'][step]
            audit(whole, 'local', step)
        binary = Path('/root/autodl-tmp/graduation_project/cuda_stage0/geogram_double_io')
        result['geogram_binary_sha256'] = hashlib.sha256(binary.read_bytes()).hexdigest()
        initial = folder/'initial.obj'
        initial.write_text(export_double(candidate['whole']), encoding='utf-8')
        for subdivision in (2, 3):
            sphere = trimesh.creation.icosphere(subdivisions=subdivision, radius=3.)
            inradius = np.einsum('ij,ij->i', sphere.face_normals, sphere.triangles[:, 0]).min()
            rows = []
            entry = dict(method=f'geogram_s{subdivision}', repeats=1, tool_radial_deficit_bound_mm=float(3-inradius), records=rows,
                         accepted_as_full_quality_delivery=False, note='无逐面误差证书；质量失败后仅诊断续跑，不是合格发布')
            result['runs'].append(entry)
            previous = initial
            for step, tool in enumerate(local_trajectory(1.8), 1):
                started = perf_counter()
                a, b = np.array([*tool.start, tool.z]), np.array([*tool.end, tool.z])
                cutter = trimesh.convex.convex_hull(np.vstack([sphere.vertices+a, sphere.vertices+b]))
                cutter_path, output = folder/f'cutter_s{subdivision}_{step}.obj', folder/f'geogram_s{subdivision}_{step}.obj'
                cutter_path.write_text(export_double(cutter), encoding='utf-8')
                command = [str(binary), str(previous), str(cutter_path), str(output)]
                with (folder/f'geogram_s{subdivision}_{step}.log').open('w', encoding='utf-8') as log:
                    proc = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=180)
                row = dict(step=step, returncode=proc.returncode, command=command, accepted=None)
                if proc.returncode or not output.exists():
                    rows.append(row)
                    save()
                    break
                mesh = trimesh.load(output, force='mesh', process=False)
                row['candidate_with_io_ms'] = (perf_counter()-started)*1000
                row.update(quality(mesh, original_keys))
                ms = pymeshlab.MeshSet()
                ms.add_mesh(pymeshlab.Mesh(mesh.vertices, mesh.faces))
                ms.compute_selection_by_self_intersections_per_face()
                row['self_intersection_flag_faces'] = int(ms.current_mesh().selected_face_number())
                row['candidate_and_diagnostics_ms'] = (perf_counter()-started)*1000
                # 检测器报警不自动判为真实自交；本轮不执行局部图域专用排除规则。
                audit(mesh, entry['method'], step)
                rows.append(row)
                previous = output
                save()
                print(entry['method'], step, row['faces'], row['changed']['bad_faces'], flush=True)
        result['status'] = 'completed'
        save()
    except Exception as exc:
        result['status'] = 'failed'
        result['errors'].append(str(exc))
        save()
        raise
    print(folder, flush=True)


if __name__ == '__main__':
    main()
