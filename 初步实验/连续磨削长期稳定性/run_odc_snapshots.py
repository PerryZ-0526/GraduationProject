"""完整千事件材料回放上的作者ODC定期快照，非每事件表面交付。"""
import argparse
import faulthandler
import json
from pathlib import Path
import shutil
import sys
import numpy as np
import pyvista as pv
from timed_paths import beijing_now, digest


def main():
    faulthandler.enable()
    parser = argparse.ArgumentParser()
    parser.add_argument('--dependencies', type=Path, required=True)
    parser.add_argument('--author', type=Path, required=True)
    parser.add_argument('--trajectory', type=Path, required=True)
    parser.add_argument('--body', choices=('thin_wall', 'gap'), required=True)
    parser.add_argument('--query', choices=('grid', 'analytic'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    frozen = args.output / '运行前冻结源码'
    frozen.mkdir()
    methods = []
    for name in ('run_odc_snapshots.py', 'odc_queries.py', 'material_state.py', 'run_extraction_ablation.py',
                 'conditioned_extraction.py', 'audit_feature_probes.py', 'timed_paths.py'):
        shutil.copyfile(Path(__file__).parent / name, frozen / name)
        methods.append({'file': name, 'sha256': digest(frozen / name)})
    for name in ('occupancy_dual_contouring.py', 'LICENSE'):
        shutil.copyfile(args.author / name, frozen / name)
    author_sha = digest(frozen / 'occupancy_dual_contouring.py')
    identity = json.loads((args.author / '01-作者代码与许可证来源.json').read_text(encoding='utf-8'))
    if author_sha != next(x['sha256'] for x in identity['files'] if x['file'] == 'occupancy_dual_contouring.py'):
        raise ValueError('作者源码身份不一致')
    plan = {'created_at_beijing': beijing_now(), 'methods': methods, 'author_identity': identity,
            'trajectory': str(args.trajectory), 'trajectory_sha256': digest(args.trajectory),
            'body': args.body, 'query': args.query, 'spacing_mm': .06, 'display_every_events': 100,
            'scope': '每100材料事件实际提取一次作者ODC；千事件材料回放，不称千次表面交付'}
    (args.output / '01-运行前固定方法与材料轨迹.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding='utf-8')
    sys.path.insert(0, str(frozen))
    sys.path.insert(0, str(args.dependencies))
    import torch
    from occupancy_dual_contouring import occupancy_dual_contouring
    from odc_queries import extract_author
    from material_state import MaterialState
    from run_extraction_ablation import metrics, analytic_residual
    from audit_feature_probes import crossings, tool_clearance
    torch.set_num_threads(1)
    source = np.load(args.trajectory)
    times, centers = source['times_s'], source['centers_mm']
    knot_times, full_knots = source['knot_times_s'], source['knots_mm']
    expected = np.column_stack([np.interp(times, knot_times, full_knots[:, i]) for i in range(3)])
    if not np.array_equal(expected, centers) or len(times) != 1001:
        raise ValueError('本版解析分段前缀必须与全部1000接收事件逐样本一致')
    state = MaterialState(args.body, .06)
    extractor = occupancy_dual_contouring('cpu')
    attempts, display_version = [], None
    with (args.output / '02-完整实际材料事件.jsonl').open('x', encoding='utf-8') as events:
        for index in range(1000):
            event = index + 1
            change = state.apply(centers[index], centers[event], .4)
            events.write(json.dumps(dict(change, event=event, time_s=float(times[event]), start_mm=centers[index].tolist(), end_mm=centers[event].tolist())) + '\n')
            events.flush()
            if event % 100:
                continue
            # 只使用当前已接收前缀，禁止将后续工具路线提前用于材料或显示。
            knots = full_knots[knot_times <= times[event]]
            if not np.any(knot_times == times[event]):
                knots = np.vstack((knots, centers[event]))
            vertices, faces, method = extract_author(torch, extractor, state.field, state.axis, knots, args.body, args.query)
            poly = pv.PolyData(vertices, np.column_stack((np.full(len(faces), 3), faces)).ravel())
            mesh_path = args.output / f'03-作者显示尝试_{event:04d}.vtp'
            poly.save(mesh_path)
            actual = pv.read(mesh_path)
            audit = metrics(actual)
            # 基础拓扑加浮点报警仍不是全量精确嵌入或连续几何证书。
            eligible = (audit['finite_vertices'] and audit['physical_degenerate_faces'] == 0 and audit['watertight']
                        and audit['winding_consistent'] and audit['components'] == (2 if args.body == 'gap' else 1)
                        and audit['self_intersection_alarm_faces'] == 0)
            if eligible:
                display_version = event
            positions = ([(x, y) for x in (-1.95, 1.95) for y in (-1.65, 1.65)] if args.body == 'thin_wall' else
                         [(y, z) for y in (-1.75, 1.75) for z in (-.75, .75)] + [(y, z) for y in (-1.5, 1.5) for z in (0, .3)])
            direction = 2 if args.body == 'thin_wall' else 0
            target = [-.18, .18] if args.body == 'thin_wall' else [-1.92, -.12, .12, 1.92]
            probes = []
            for fixed in positions:
                clearance = tool_clearance(direction, fixed, knots)
                if clearance <= 0:
                    raise ValueError('初态特征射线前缀不满足未切削前提')
                values = crossings(actual, direction, fixed)
                error = None if len(values['crossings_mm']) != len(target) else float(np.max(np.abs(np.asarray(values['crossings_mm']) - target)))
                probes.append(dict(values, fixed_coordinates_mm=fixed, crossing_error_max_mm=error))
            attempts.append({'material_version': event, 'knots_prefix_mm': knots.tolist(), 'method': method,
                             'file': str(mesh_path), 'sha256': digest(mesh_path), 'metrics': audit,
                             'basic_display_eligible': bool(eligible), 'display_version_after': display_version,
                             'display_age_events': None if display_version is None else event - display_version,
                             'feature_probes': probes, 'analytic_vertex_residual': analytic_residual(actual, args.body, knots, .4)})
            record = {'updated_at_beijing': beijing_now(), 'status': 'running', 'planned_events': 1000,
                      'planned_snapshots': 10, 'material_version': event, 'attempts': attempts,
                      'torch_version': torch.__version__, 'torch_default_dtype': str(torch.get_default_dtype())}
            (args.output / '04-作者连续快照记录.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
    np.savez(args.output / '05-最终实际材料场.npz', field=state.field, axis_mm=state.axis)
    if digest(args.trajectory) != plan['trajectory_sha256'] or digest(frozen / 'occupancy_dual_contouring.py') != author_sha:
        raise ValueError('原轨迹或作者源码改变')
    if any(digest(frozen / item['file']) != item['sha256'] for item in methods):
        raise ValueError('实际冻结方法改变')
    record.update(status='complete', updated_at_beijing=beijing_now())
    (args.output / '04-作者连续快照记录.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'body': args.body, 'query': args.query, 'material_events': 1000, 'snapshots': len(attempts),
                      'eligible': sum(x['basic_display_eligible'] for x in attempts)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
