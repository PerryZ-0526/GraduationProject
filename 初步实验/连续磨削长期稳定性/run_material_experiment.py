"""执行材料状态长序列开发批次；不把材料更新当作完整网格维护成功。"""
import argparse
import json
from pathlib import Path
from time import perf_counter
import numpy as np
import pyvista as pv
from material_state import MaterialState
from timed_paths import beijing_now, digest, save_assets


def extract_mesh(state, path):
    image = pv.ImageData(dimensions=state.field.shape, spacing=(state.spacing,) * 3,
                         origin=(state.axis[0],) * 3)
    image.point_data['material'] = state.field.ravel(order='F')
    mesh = image.contour([0], scalars='material').triangulate()
    mesh.save(path)
    return {'vertices': mesh.n_points, 'faces': mesh.n_cells,
            'open_edges': mesh.n_open_edges, 'sha256': digest(path),
            'audit_scope': '仅提取数量及开放边，尚无精确嵌入或PaMO审计'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--spacing', type=float, default=0.12)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    manifest = save_assets(args.output / '时间轨迹')
    rows, finals = [], {}
    for body in manifest['bodies']:
        finals[body] = {}
        for asset in manifest['assets']:
            data = np.load(args.output / '时间轨迹' / asset['file'])
            state = MaterialState(body, args.spacing)
            started = perf_counter()
            events = []
            folder = args.output / f"{body}_{asset['rate_hz']}Hz"
            folder.mkdir()
            # 逐事件落盘，进程中断仍保留实际已完成的事件，不补造受阻成功。
            with (folder / '01-材料更新事件.jsonl').open('x', encoding='utf-8') as log:
                for eid, (start, end) in enumerate(zip(data['centers_mm'][:-1], data['centers_mm'][1:])):
                    tick = perf_counter()
                    event = state.apply(start, end, manifest['radius_mm'])
                    event.update(event_id=eid, simulation_time_s=float(data['times_s'][eid + 1]),
                                 update_ms=(perf_counter() - tick) * 1000)
                    events.append(event)
                    log.write(json.dumps(event, ensure_ascii=False) + '\n')
            elapsed = perf_counter() - started
            # 同一分段直线的十段整体扫掠应覆盖所有采样事件，核对时间步依赖。
            reference = state.rebuild(data['knots_mm'][:-1], data['knots_mm'][1:], manifest['radius_mm'])
            difference = float(np.max(np.abs(reference - state.field)))
            robust = (np.abs(reference) > 1e-12) & (np.abs(state.field) > 1e-12)
            mismatch = int(np.count_nonzero(((reference < 0) != (state.field < 0)) & robust))
            final_path = folder / '02-最终材料场.npz'
            np.savez_compressed(final_path, field=state.field, axis_mm=state.axis)
            mesh_info = extract_mesh(state, folder / '03-最终提取网格.vtp')
            repeat = state.field.copy()
            for start, end in zip(data['knots_mm'][:-1], data['knots_mm'][1:]):
                state.apply(start, end, manifest['radius_mm'])
            timings = np.array([event['update_ms'] for event in events])
            row = {'body': body, 'rate_hz': asset['rate_hz'], 'events': len(events),
                   'positive_node_removal_events': sum(e['removed_negative_nodes'] > 0 for e in events),
                   'field_change_events': sum(e['changed_nodes'] > 0 for e in events),
                   'remaining_negative_nodes': int(np.count_nonzero(state.field < 0)),
                   'removed_negative_nodes': int(np.count_nonzero((state.initial < 0) & (repeat >= 0))),
                   'node_volume_proxy_mm3': float(np.count_nonzero((state.initial < 0) & (repeat >= 0)) * state.spacing ** 3),
                   'volume_scope': '格点数乘单元体积的代理量，不是精确去除体积',
                   'wall_time_s_including_event_logging': elapsed,
                   'update_ms_p50_p95_p99': np.percentile(timings, [50, 95, 99]).tolist(),
                   'allocated_state_array_bytes': state.points.nbytes + state.initial.nbytes + state.field.nbytes,
                   'memory_scope': '持有数组之和，非进程峰值内存',
                   'prefix_field_max_difference_mm': difference, 'robust_sign_mismatches': mismatch,
                   'near_zero_nodes_excluded': int(np.count_nonzero(~robust)),
                   'repeated_whole_sweep_max_difference_mm': float(np.max(np.abs(state.field - repeat))),
                   'field_sha256': digest(final_path), 'mesh': mesh_info,
                   'complete_mesh_pipeline_executed': False}
            rows.append(row)
            finals[body][asset['rate_hz']] = repeat
            record = {'updated_at_beijing': beijing_now(), 'status': 'running',
                      'scope': '独立材料状态开发，未接Geogram/PaMO', 'rows': rows}
            (args.output / '01-材料长序列记录.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
            print(json.dumps(row, ensure_ascii=False), flush=True)
    comparisons = []
    for body, fields in finals.items():
        for rate in (30, 60):
            comparisons.append({'body': body, 'baseline_hz': 10, 'compared_hz': rate,
                                'max_field_difference_mm': float(np.max(np.abs(fields[10] - fields[rate])))})
    record.update(status='complete', updated_at_beijing=beijing_now(), rate_comparisons=comparisons)
    (args.output / '01-材料长序列记录.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
