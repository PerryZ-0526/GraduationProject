"""冻结四方法的新姿态完整材料事件与定期表面评价。"""
import argparse
import faulthandler
import json
from pathlib import Path
import sys
import traceback
import numpy as np
import pyvista as pv
from timed_paths import beijing_now, digest


def main():
    faulthandler.enable()
    parser = argparse.ArgumentParser()
    parser.add_argument('--asset', type=Path, required=True)
    parser.add_argument('--body', choices=('thin_wall', 'gap'), required=True)
    parser.add_argument('--dependencies', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    frozen = Path(__file__).parent
    names = ('run_pose_route.py', 'pose_material.py', 'material_state.py', 'conditioned_extraction.py',
             'run_extraction_ablation.py', 'audit_feature_probes.py', 'timed_paths.py', 'occupancy_dual_contouring.py')
    plan = {'created_at_beijing': beijing_now(), 'body': args.body, 'asset': str(args.asset),
            'asset_sha256': digest(args.asset), 'methods': [{'file': name, 'sha256': digest(frozen / name)} for name in names],
            'parameters': {'spacing_mm': .06, 'radius_mm': .4, 'display_every_events': 100,
                           'odc_num_grid': 120, 'odc_batch_size': 1000000, 'odc_other_parameters': '作者默认'},
            'scope': '完整1000材料事件、每100事件四方法表面尝试；非每事件或临床交付'}
    (args.output / '01-实际执行输入与方法绑定.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding='utf-8')
    sys.path.insert(0, str(args.dependencies))
    import torch
    from occupancy_dual_contouring import occupancy_dual_contouring
    from pose_material import PoseMaterial, extract_pose, feature_review
    from material_state import initial_field, capsule_field
    from conditioned_extraction import extract
    from run_extraction_ablation import metrics
    torch.set_num_threads(1)
    asset = np.load(args.asset)
    times, centers = asset['times_s'], asset['centers_mm']
    knot_times, full_knots = asset['knot_times_s'], asset['knots_mm']
    if len(times) != 1001 or not np.array_equal(centers, np.column_stack([np.interp(times, knot_times, full_knots[:, i]) for i in range(3)])):
        raise ValueError('轨迹采样与真实分段输入不一致')
    state = PoseMaterial(args.body, asset['rotation'], asset['shift_mm'])
    extractor = occupancy_dual_contouring('cpu')
    attempts = []
    display_versions = dict.fromkeys(('vtk_raw', 'vtk_zero', 'odc_grid', 'odc_analytic'))
    with (args.output / '02-完整实际材料事件.jsonl').open('x', encoding='utf-8') as events:
        for index in range(1000):
            event = index + 1
            change = state.apply(centers[index], centers[event], .4)
            events.write(json.dumps(dict(change, event=event, time_s=float(times[event]))) + '\n')
            events.flush()
            if event % 100:
                continue
            knots = full_knots[knot_times <= times[event]]
            for method in display_versions:
                try:
                    if method.startswith('vtk'):
                        poly, info = extract(state.field, state.axis, True, method == 'vtk_zero')
                    else:
                        vertices, faces, counts = extract_pose(torch, extractor, state, knots, method.split('_')[1])
                        poly = pv.PolyData(vertices, np.column_stack((np.full(len(faces), 3), faces)).ravel())
                        info = {'query_source': method.split('_')[1], 'query_counts': counts,
                                'author_parameters_modified': False, 'torch_default_dtype': str(torch.get_default_dtype())}
                    file = args.output / f'显示尝试_{event:04d}_{method}.vtp'
                    poly.save(file)
                    actual = pv.read(file)
                    audit = metrics(actual)
                    eligible = (audit['finite_vertices'] and audit['physical_degenerate_faces'] == 0 and audit['watertight']
                                and audit['winding_consistent'] and audit['components'] == (2 if args.body == 'gap' else 1)
                                and audit['self_intersection_alarm_faces'] == 0)
                    if eligible:
                        display_versions[method] = event
                    probes = feature_review(actual, state, knots)
                    values = initial_field((np.asarray(actual.points) - state.shift) @ state.rotation, args.body)
                    for a, b in zip(knots[:-1], knots[1:]):
                        values = np.maximum(values, -capsule_field(actual.points, a, b, .4))
                    row = {'method': method, 'material_version': event, 'status': 'saved_and_reviewed',
                           'file': str(file), 'sha256': digest(file), 'identity': info, 'metrics': audit,
                           'basic_display_eligible': bool(eligible), 'feature_probes': probes,
                           'analytic_vertex_residual_max': float(np.max(np.abs(values))),
                           'display_version_after': display_versions[method]}
                except Exception as error:
                    # 实际方法异常留在完整分母，其余方法和材料事件继续，不改参数重试。
                    row = {'method': method, 'material_version': event, 'status': 'execution_failed',
                           'error': f'{type(error).__name__}: {error}', 'display_version_after': display_versions[method]}
                    with (args.output / '方法异常.log').open('a', encoding='utf-8') as log:
                        log.write(traceback.format_exc())
                attempts.append(row)
            record = {'updated_at_beijing': beijing_now(), 'status': 'running', 'material_version': event,
                      'planned_material_events': 1000, 'planned_surface_attempts': 40, 'attempts': attempts,
                      'torch_version': torch.__version__, 'display_versions': dict(display_versions)}
            (args.output / '03-实际四方法完整记录.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
    np.savez(args.output / '04-最终材料场.npz', field=state.field, axis_mm=state.axis)
    if digest(args.asset) != plan['asset_sha256'] or any(digest(frozen / item['file']) != item['sha256'] for item in plan['methods']):
        raise ValueError('固定输入或实际冻结方法改变')
    record.update(status='complete', updated_at_beijing=beijing_now())
    (args.output / '03-实际四方法完整记录.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'body': args.body, 'events': 1000, 'attempts': len(attempts),
                      'saved': sum(x['status'] == 'saved_and_reviewed' for x in attempts)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
