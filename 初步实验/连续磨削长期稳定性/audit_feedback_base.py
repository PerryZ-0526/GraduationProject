"""流式汇总基座事件，核查文件摘要、分母、父链和旧参照等价性。"""
import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import statistics
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / '连续磨削实验基座'))
from event_store import atomic_json, digest, now, read_json, require_file


def audit(folder, legacy=None):
    binding = read_json(folder / '01-运行绑定.json')['binding']
    status = read_json(folder / '05-运行状态.json')
    groups = {(route, branch): [] for route in binding['plans'] for branch in binding.get('branches', ['full', 'candidate'])}
    expected_parents = {}
    states, timing_rows, curve, comparisons, quality_rows = {}, [], [], [], []
    previous, boolean_count, total, inherited = '0' * 64, 0, 0, 0
    index = folder / '02-事件索引.jsonl'
    if index.exists():
        with index.open('rb') as stream:
            for line in stream:
                if not line.endswith(b'\n'):
                    break
                item = json.loads(line)
                path = folder / item['record_file']
                if item['seq'] != total or item['previous'] != previous or digest(path) != item['record_sha256']:
                    raise ValueError('索引或事件摘要变化')
                previous = hashlib.sha256(line).hexdigest()
                detail = read_json(path)
                inherited += int(detail.get('origin') is not None)
                route, event = detail['route'], detail['event']
                position = states.get(route, {}).get('next_index', 0)
                if detail['event_index'] != position or binding['plans'][route][position] != event:
                    raise ValueError('完整计划事件顺序不一致')
                states[route] = detail['state']
                rrow = detail['rows'][0]
                timings = dict(detail['timings_ms'])
                boolean_count += rrow.get('recovery', {}).get('boolean_count', 0)
                if rrow['status'] == 'reference_valid':
                    reference = require_file(detail['state']['reference']['mesh'])
                    if legacy:
                        old = legacy / (route + '_' + event + '_reference') / 'validated_reference.obj'
                        if old.exists():
                            comparisons.append({'route': route, 'event': event,
                                'old_reference_sha256': digest(old), 'new_reference_sha256': digest(reference),
                                'byte_identical': digest(old) == digest(reference)})
                for row in detail['rows'][1:]:
                    key = route, row['branch']
                    expected = expected_parents.get(key)
                    if expected and row.get('parent_sha256') and row['parent_sha256'] != expected:
                        raise ValueError('质量分支父链不一致')
                    if row['status'] == 'published_under_sampled_and_vertex_protocol':
                        output = {'path': row['output_file'], 'sha256': row['output_sha256']}
                        require_file(output)
                        if output != detail['state']['parents'][row['branch']]:
                            raise ValueError('已发布对象与检查点不一致')
                        expected_parents[key] = output['sha256']
                        chosen = next((attempt for attempt in row.get('attempts', [])
                                       if attempt.get('output_sha256') == output['sha256'] and attempt.get('status') == 'accepted_sampled'), None)
                        if chosen and 'quality' in chosen and 'source_quality' in chosen:
                            output_quality, source_quality = chosen['quality'], chosen['source_quality']
                            point = {'route': route, 'event': event, 'branch': row['branch'],
                                     'source_faces': source_quality['total_faces'], 'output_faces': output_quality['total_faces']}
                            # 各帧比较自己的同次输入，不将不同父链混成一组配对收益。
                            for metric in ('angle_below_10_deg', 'angle_below_5_deg', 'angle_below_1_deg', 'high_quality_25_deg_q_0_4'):
                                for field in ('faces', 'fraction', 'area_fraction'):
                                    point['source_' + metric + '_' + field] = source_quality[metric][field]
                                    point['output_' + metric + '_' + field] = output_quality[metric][field]
                            quality_rows.append(point)
                    for name in ('base_quality_wall_ms', 'base_output_audit_wall_ms', 'pamo_run_ms', 'safe_projection_ms'):
                        values = [attempt[name] for attempt in row.get('attempts', []) if isinstance(attempt.get(name), (int, float))]
                        if values:
                            timings[row['branch'] + '_' + name] = sum(values)
                    groups[key].append({key: value for key, value in row.items()
                                        if key in ('event', 'status', 'published_version', 'cumulative_geometry')})
                    geometry = row.get('cumulative_geometry')
                    if geometry:
                        sampled = geometry['sampled']
                        curve.append({'route': route, 'event': event, 'branch': row['branch'],
                            'probe_max_mm': geometry['probe_max_mm'], 'sampled_max_mm': sampled['sampled_max_mm'],
                            'forward_p95_mm': sampled['pamo_to_reference']['p95_mm'],
                            'reverse_p95_mm': sampled['reference_to_pamo']['p95_mm'],
                            'forward_rms_mm': sampled['pamo_to_reference']['rms_mm'],
                            'reverse_rms_mm': sampled['reference_to_pamo']['rms_mm']})
                timing_rows.append(timings)
                total += 1
    branches = []
    for (route, branch), rows in groups.items():
        counts = Counter(row['status'] for row in rows)
        measured = [point for point in curve if point['route'] == route and point['branch'] == branch]
        failed = [row for row in rows if row['status'] not in
                  ('published_under_sampled_and_vertex_protocol', 'contained_reused_parent', 'blocked_by_previous_failure')]
        branches.append({'route': route, 'branch': branch, 'planned': len(binding['plans'][route]),
            'committed': len(rows), 'unexecuted': len(binding['plans'][route]) - len(rows), 'statuses': dict(counts),
            'first_algorithm_stop': {'event': failed[0]['event'], 'status': failed[0]['status']} if failed else None,
            'largest_probe_observation': max(measured, key=lambda point: point['probe_max_mm'], default=None)})
    stages = sorted({stage for row in timing_rows for stage in row})
    bytes_written = index.stat().st_size if index.exists() else 0
    bytes_written += sum((folder / item).stat().st_size for item in ['03-检查点.json', '04-当前事件.json'] if (folder / item).exists())
    bytes_written += sum(path.stat().st_size for path in (folder / 'events').glob('*.json'))
    complete = total == sum(len(plan) for plan in binding['plans'].values())
    quality_summary = []
    for (route, branch) in groups:
        rows = [point for point in quality_rows if point['route'] == route and point['branch'] == branch]
        quality_summary.append({'route': route, 'branch': branch, 'measured_outputs': len(rows),
            'median_output_face_fraction': {metric: statistics.median(point['output_' + metric + '_fraction'] for point in rows)
                for metric in ('angle_below_10_deg', 'angle_below_5_deg', 'angle_below_1_deg', 'high_quality_25_deg_q_0_4')} if rows else {},
            'comparison_scope': '各帧同次输入及实际输出；三档小角为主、25度和q为辅，同时CSV保留面数及面积占比'})
    return {'time_beijing': now(), 'execution_status': status['status'], 'complete_plan': complete,
        'committed_events': total, 'planned_events': sum(len(plan) for plan in binding['plans'].values()),
        'inherited_prefix_events': inherited, 'new_framework_events': total - inherited, 'fork': binding.get('fork'),
        'geometry_policy': binding['geometry_policy'], 'branches': branches,
        'reference_boolean_count': boolean_count, 'old_reference_comparisons': comparisons,
        'all_compared_references_byte_identical': all(item['byte_identical'] for item in comparisons) if comparisons else None,
        'ledger_and_checkpoint_bytes': bytes_written,
        'stage_median_ms': {stage: statistics.median(row[stage] for row in timing_rows if stage in row) for stage in stages},
        'quality_summary': quality_summary,
        'claim_scope': '摘要与父链核对、有限探针和运行统计；不是连续距离或临床精度证书'}, curve, quality_rows


def plot(folder, summary, curve):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    routes = list(dict.fromkeys(row['route'] for row in summary['branches']))
    figure, axes = plt.subplots(len(routes), 3, figsize=(13, 3.4 * len(routes)), squeeze=False)
    for i, route in enumerate(routes):
        for branch in ('full', 'candidate'):
            rows = [row for row in curve if row['route'] == route and row['branch'] == branch]
            x = [int(row['event'][1:]) + 1 for row in rows]
            for j, (label, values) in enumerate([
                ('Maximum probe', [row['probe_max_mm'] for row in rows]),
                ('Directional P95', [max(row['forward_p95_mm'], row['reverse_p95_mm']) for row in rows]),
                ('Directional RMS', [max(row['forward_rms_mm'], row['reverse_rms_mm']) for row in rows])]):
                if rows:
                    axes[i, j].plot(x, values, label=branch)
                axes[i, j].set_title(route + '\n' + label)
                axes[i, j].set_xlabel('Cutting event number')
                axes[i, j].set_ylabel('Distance (mm)')
                axes[i, j].grid(alpha=.2)
        for axis in axes[i]:
            if axis.lines:
                axis.legend()
            else:
                axis.text(.5, .5, 'No committed outputs', ha='center', va='center', transform=axis.transAxes)
    figure.suptitle(summary['execution_status'] + ' | finite probes only; reference discretization error unknown')
    figure.tight_layout(rect=(0, 0, 1, .94))
    destination = folder / '10-偏差统计图'
    destination.mkdir(exist_ok=True)
    figure.savefig(destination / '01-累计偏差统计.png', dpi=180)
    figure.savefig(destination / '01-累计偏差统计.pdf')
    plt.close(figure)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--folder', type=Path, required=True)
    parser.add_argument('--legacy', type=Path)
    parser.add_argument('--plot', action='store_true')
    args = parser.parse_args()
    result, curve, quality_rows = audit(args.folder, args.legacy)
    atomic_json(args.folder / '08-基座运行统计与父链审计.json', result)
    if curve:
        with (args.folder / '09-逐帧偏差统计.csv').open('w', encoding='utf-8-sig', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(curve[0]))
            writer.writeheader()
            writer.writerows(curve)
    if quality_rows:
        with (args.folder / '11-逐帧网格质量统计.csv').open('w', encoding='utf-8-sig', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(quality_rows[0]))
            writer.writeheader()
            writer.writerows(quality_rows)
    if args.plot:
        plot(args.folder, result, curve)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
