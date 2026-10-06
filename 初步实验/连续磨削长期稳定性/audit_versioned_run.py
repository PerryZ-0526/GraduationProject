"""终态后逐张重读显示尝试，核查完整事件、恢复父状态与材料一致性。"""
import argparse
import json
from pathlib import Path
import sys
import numpy as np
import pyvista as pv
from timed_paths import beijing_now, digest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--previous-material', type=Path, required=True)
    args = parser.parse_args()
    output = args.input / '03-逐事件终态保存对象完整复审.json'
    if output.exists():
        raise ValueError('复审文件禁止覆盖')
    original_phases = args.input / '02-实际阶段退出记录.json'
    phases = json.loads(original_phases.read_text(encoding='utf-8'))
    supplemental = args.input / '05-八阶段实际终态只读核对.json'
    if supplemental.exists():
        # 汇总器自身终态写入失败时只接受绑定原记录的追加证据，原失败与字节保持。
        actual = json.loads(supplemental.read_text(encoding='utf-8'))
        if actual['original_record_sha256'] != digest(original_phases) or actual['rows'] != phases['rows']:
            raise ValueError('追加终态未绑定原八阶段记录')
        phases = actual
    if phases['status'] != 'complete_execution_ledger' or len(phases['rows']) != 8 or any(x['returncode'] for x in phases['rows']):
        raise ValueError('八阶段尚未完整成功退出，不能登记完整复审')
    # 使用该批实际冻结检查器，不能混用随后改动的工作区版本。
    sys.path.insert(0, str(args.input / '批次启动前源码'))
    from run_versioned_material import display_audit
    rows = []
    for body in ('thin_wall', 'gap'):
        for zero in (False, True):
            folder = args.input / f'{body}_zero{int(zero)}'
            record = json.loads((folder / '06-状态记录.json').read_text(encoding='utf-8'))
            plan = json.loads((folder / '01-运行前固定输入与方法.json').read_text(encoding='utf-8'))
            checkpoint = json.loads((folder / '05-检查点指针.json').read_text(encoding='utf-8'))
            prefix = json.loads((folder / '阶段_0500_状态快照.json').read_text(encoding='utf-8'))
            config = plan['config']
            total = config['planned_events']
            trajectory = np.load(config['trajectory'])
            times, centers = trajectory['times_s'], trajectory['centers_mm']
            received = [json.loads(x) for x in (folder / '02-完整接收事件.jsonl').read_text(encoding='utf-8').splitlines()]
            applied = [json.loads(x) for x in (folder / '03-实际材料事件.jsonl').read_text(encoding='utf-8').splitlines()]
            events = all(x['event'] == i + 1 and x['time_s'] == times[i + 1]
                         and np.array_equal(x['start_mm'], centers[i]) and np.array_equal(x['end_mm'], centers[i + 1])
                         for i, x in enumerate(received))
            events &= len(received) == total and [x['event'] for x in applied] == list(range(1, total + 1))
            files_match = digest(config['trajectory']) == config['trajectory_sha256']
            files_match &= digest(folder / '02-完整接收事件.jsonl') == checkpoint['received_sha256']
            files_match &= digest(folder / checkpoint['file']) == checkpoint['sha256']
            files_match &= all(digest(folder / '运行前冻结源码' / x['file']) == x['sha256'] for x in plan['methods'])
            snapshots = record['display_attempts']
            order = [x['material_version'] for x in snapshots] == list(range(config['display_every_events'], total + 1, config['display_every_events']))
            display_version = None
            saved_reviews = []
            for attempt in snapshots:
                mesh_file = folder / attempt['file']
                audit = display_audit(pv.read(mesh_file), body)
                same = digest(mesh_file) == attempt['sha256'] and audit == attempt['audit']
                if audit['basic_display_eligible']:
                    display_version = attempt['material_version']
                expected_age = None if display_version is None else attempt['material_version'] - display_version
                expected_time = None if display_version is None else float(times[attempt['material_version']] - times[display_version])
                same &= attempt['display_version_after'] == display_version and attempt['display_age_events'] == expected_age and attempt['display_age_path_seconds'] == expected_time
                saved_reviews.append({'material_version': attempt['material_version'], 'matched': bool(same),
                                      'basic_display_eligible': audit['basic_display_eligible']})
            field = np.load(folder / checkpoint['file'])['field']
            reference = np.load(args.previous_material / f'{body}_10Hz/02-最终材料场.npz')['field']
            prefix_match = snapshots[:len(prefix['display_attempts'])] == prefix['display_attempts']
            state_match = record['status'] == 'complete' and record['material_version'] == total and record['resumed_from_version'] == 500 and record['display_version'] == display_version
            same_field = bool(np.array_equal(field, reference))
            passed = events and files_match and order and prefix_match and state_match and same_field and all(x['matched'] for x in saved_reviews)
            rows.append({'body': body, 'zero': zero, 'complete_contract_matched': bool(passed),
                         'events_applied': len(applied), 'positive_removal_node_events': sum(x['removed_negative_nodes'] > 0 for x in applied),
                         'saved_reviews': saved_reviews, 'material_bitwise_equal_to_uninterrupted': same_field,
                         'final_display_version': display_version})
            print(json.dumps({'body': body, 'zero': zero, 'matched': bool(passed), 'saved_reviews': len(saved_reviews)}, ensure_ascii=False), flush=True)
    result = {'updated_at_beijing': beijing_now(), 'rows': rows, 'reviewer_sha256': digest(__file__),
              'scope': '实际保存对象基础审计和材料/显示契约；不是完整自交、连续几何或临床交付验收'}
    with output.open('x', encoding='utf-8') as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)


if __name__ == '__main__':
    main()
