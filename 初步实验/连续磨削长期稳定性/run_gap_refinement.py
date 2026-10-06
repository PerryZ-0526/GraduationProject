"""同一十段连续扫掠的窄缝分辨率诊断，不计作千步反馈成功。"""
import argparse
import json
from pathlib import Path
import shutil
import time
import numpy as np
import pyvista as pv
from material_state import MaterialState
from conditioned_extraction import extract
from audit_feature_probes import crossings, tool_clearance
from timed_paths import beijing_now, digest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--trajectory', type=Path, required=True)
    parser.add_argument('--spacing', type=float, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    frozen = args.output / '运行前冻结源码'
    frozen.mkdir()
    methods = []
    for name in ('run_gap_refinement.py', 'material_state.py', 'conditioned_extraction.py',
                 'audit_feature_probes.py', 'timed_paths.py'):
        shutil.copyfile(Path(__file__).parent / name, frozen / name)
        methods.append({'file': name, 'sha256': digest(frozen / name)})
    trajectory_sha = digest(args.trajectory)
    plan = {'created_at_beijing': beijing_now(), 'spacing_mm': args.spacing,
            'trajectory': str(args.trajectory), 'trajectory_sha256': trajectory_sha,
            'methods': methods, 'planned_segments': 10,
            'scope': '同一解析十段扫掠的分辨率隔离诊断，非千步逐帧或GPU实验'}
    (args.output / '01-运行前输入与源码冻结.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding='utf-8')
    knots = np.load(args.trajectory)['knots_mm']
    started = time.perf_counter()
    state = MaterialState('gap', args.spacing)
    events = []
    for index, (a, b) in enumerate(zip(knots[:-1], knots[1:])):
        events.append(dict(state.apply(a, b, .4), segment=index))
    material_elapsed = time.perf_counter() - started
    field_file = args.output / '02-同轨迹材料场.npz'
    np.savez_compressed(field_file, field=state.field, axis_mm=state.axis)
    field_sha = digest(field_file)
    rows = []
    for zero in (False, True):
        mesh, info = extract(state.field, state.axis, True, zero)
        file = args.output / f'03-结构网格近零{int(zero)}.vtp'
        mesh.save(file)
        actual = pv.read(file)
        triangles = np.asarray(actual.points, dtype=np.float64)[actual.faces.reshape(-1, 4)[:, 1:]]
        area = np.linalg.norm(np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0]), axis=1) * .5
        probes = []
        for fixed in ([(y, z) for y in (-1.75, 1.75) for z in (-.75, .75)]
                      + [(y, z) for y in (-1.5, 1.5) for z in (0, .3)]):
            clearance = tool_clearance(0, fixed, knots)
            if clearance <= 0:
                raise ValueError('初态参照射线可能被切削')
            values = crossings(actual, 0, fixed)
            crossing = values['crossings_mm']
            error = None if len(crossing) != 4 else float(np.max(np.abs(np.asarray(crossing) - [-1.92, -.12, .12, 1.92])))
            probes.append(dict(values, fixed_coordinates_mm=fixed, crossing_error_max_mm=error,
                               tool_clearance_lower_bound_mm=clearance))
        rows.append({'method': info, 'file': str(file), 'sha256': digest(file),
                     'faces': actual.n_cells, 'physical_degenerate_faces': int(np.count_nonzero(area <= 1e-12)),
                     'probes': probes, 'exact_embedding_certificate': False})
    # 同一保存对象和冻结方法终态核对，不把两种提取配置当作独立材料算法。
    if digest(field_file) != field_sha or digest(args.trajectory) != trajectory_sha:
        raise ValueError('材料或轨迹摘要改变')
    if any(digest(frozen / item['file']) != item['sha256'] for item in methods):
        raise ValueError('冻结方法改变')
    result = {'updated_at_beijing': beijing_now(), 'status': 'complete', 'spacing_mm': args.spacing,
              'material_sha256': field_sha, 'material_computation_seconds': material_elapsed,
              'segment_events': events, 'rows': rows, 'scope': plan['scope']}
    (args.output / '04-细分诊断完整记录.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'spacing': args.spacing, 'segments': len(events),
                      'degenerate_faces': [r['physical_degenerate_faces'] for r in rows],
                      'max_probe_error': [max(p['crossing_error_max_mm'] for p in r['probes']) for r in rows]}, ensure_ascii=False))


if __name__ == '__main__':
    main()
