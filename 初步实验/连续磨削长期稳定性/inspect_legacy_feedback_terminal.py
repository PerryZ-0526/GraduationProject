"""保留旧账本原字节，单列执行句柄终止和实际完整事件前缀。"""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / '连续磨削实验基座'))
from event_store import atomic_json, digest, now, read_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--folder', type=Path, required=True)
    parser.add_argument('--prepared', type=Path, required=True)
    args = parser.parse_args()
    path = args.folder / '01-反馈执行与独立审计.json'
    data = read_json(path)
    manifest = read_json(args.prepared / '01-完整范围冻结清单.json')
    groups = []
    for route in manifest['routes']:
        if route['split'] != 'long':
            continue
        for branch in ('R', 'full', 'candidate'):
            rows = [row for row in data['rows'] if row['route'] == route['id'] and row['branch'] == branch]
            measured = [row for row in rows if 'cumulative_geometry' in row]
            worst = max(measured, key=lambda row: row['cumulative_geometry']['probe_max_mm'], default=None)
            groups.append({'route': route['id'], 'branch': branch, 'planned': len(route['cutting_prefix_ids']),
                'recorded': len(rows), 'last_event': rows[-1]['event'] if rows else None,
                'statuses': dict(Counter(row['status'] for row in rows)),
                'worst_observation': {'event': worst['event'], 'geometry': worst['cumulative_geometry']} if worst else None,
                'reference_replayed_booleans': sum(len(row.get('recovery', {}).get('runs', [])) for row in rows),
                'first_guarded_reference': next((row['event'] for row in rows if row.get('recovery', {}).get('accepted')), None)})
    result = {'time_beijing': now(), 'original_record': str(path), 'original_sha256': digest(path),
        'original_bytes': path.stat().st_size, 'original_status_field': data['status'],
        'actual_execution_handle': 88585, 'actual_exit_code': 1,
        'actual_terminal_error': 'paramiko SFTP put/open 抛出 OSError: Failure，执行句柄终态已核实',
        'cause_scope': '写入失败的底层原因未确认；不能据此认定磁盘写满或几何超限',
        'groups': groups, 'planned_events': 768,
        'original_record_unchanged': True, 'full_batch_completed': False}
    atomic_json(args.folder / '07-实际环境中断与最后完整前缀.json', result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
