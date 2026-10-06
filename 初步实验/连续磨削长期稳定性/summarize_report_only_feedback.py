"""按完整计划分母统计只报告几何偏差的反馈批次，运行中与终态明确区分。"""
import argparse
from collections import Counter
import csv
import json
from pathlib import Path


def summarize(folder, prepared):
    record = json.loads((folder / '01-反馈执行与独立审计.json').read_text(encoding='utf-8'))
    manifest = json.loads((prepared / '01-完整范围冻结清单.json').read_text(encoding='utf-8'))
    plans = {route['id']: len(route['cutting_prefix_ids']) for route in manifest['routes'] if route['split'] == 'long'}
    result = {'execution_status': record['status'],
              'complete': record['status'] == 'completed_with_recorded_failures', 'branches': []}
    curve = []
    for route, planned in plans.items():
        for branch in ('full', 'candidate'):
            rows = [row for row in record['rows'] if row['route'] == route and row['branch'] == branch]
            statuses = Counter(row['status'] for row in rows)
            published = [row for row in rows if row['status'] == 'published_under_sampled_and_vertex_protocol']
            failures = [row for row in rows if row['status'] not in
                        ('published_under_sampled_and_vertex_protocol', 'contained_reused_parent', 'blocked_by_previous_failure')]
            # 仅统计已得到参照的实际输出，不给未运行或失败帧补造偏差。
            measured = []
            for row in rows:
                geometry = row.get('cumulative_geometry')
                if geometry is None:
                    continue
                sampled = geometry['sampled']
                item = {'route': route, 'branch': branch, 'event': row['event'], 'status': row['status'],
                        'probe_max_mm': geometry['probe_max_mm'],
                        'sampled_max_mm': sampled['sampled_max_mm'],
                        'forward_p95_mm': sampled['pamo_to_reference']['p95_mm'],
                        'reverse_p95_mm': sampled['reference_to_pamo']['p95_mm'],
                        'forward_rms_mm': sampled['pamo_to_reference']['rms_mm'],
                        'reverse_rms_mm': sampled['reference_to_pamo']['rms_mm']}
                measured.append(item)
                curve.append(item)
            worst = max(measured, key=lambda item: item['probe_max_mm'], default=None)
            result['branches'].append({'route': route, 'branch': branch, 'planned': planned,
                'recorded': len(rows), 'statuses': dict(statuses), 'published': len(published),
                'last_published_event': published[-1]['event'] if published else None,
                'first_stop': {'event': failures[0]['event'], 'status': failures[0]['status']} if failures else None,
                'measured_published_outputs': len(measured), 'largest_probe_observation': worst})
    return result, curve


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--folder', type=Path, required=True)
    parser.add_argument('--prepared', type=Path, required=True)
    parser.add_argument('--save', action='store_true')
    args = parser.parse_args()
    result, curve = summarize(args.folder, args.prepared)
    if args.save:
        # 观察报告不覆盖执行账本；完整性和终止原因以实际控制器记录为准。
        (args.folder / '03-连续长度与偏差观察.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        if curve:
            with (args.folder / '04-逐帧累计偏差.csv').open('w', encoding='utf-8-sig', newline='') as stream:
                writer = csv.DictWriter(stream, fieldnames=list(curve[0]))
                writer.writeheader()
                writer.writerows(curve)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
