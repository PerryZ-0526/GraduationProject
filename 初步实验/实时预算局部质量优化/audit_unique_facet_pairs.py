"""对实际保存数组重新精确复审；有界辅助对应只用于比较，不改原输出。"""
from pathlib import Path
import argparse
import datetime
import hashlib
import json
import numpy as np
from exact_mesh_memory import ExactMeshMemory
from triangle_correspondence_bound import certify_with_virtual_snap
from verify_triangle_correspondence_bound import control_checks


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    args = parser.parse_args()
    record = args.source / '01-唯一面扫描同源完整对照.json'
    original = json.loads(record.read_text(encoding='utf-8'))
    assert original['status'] == 'completed' and len(original['rows']) == 27
    assert original['pair_count'] == 162
    full = ExactMeshMemory()
    report = {'time_beijing': datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
              'status': 'running', 'source_sha256': sha(record), 'controls': control_checks(), 'rows': [],
              'method_sha256': {name: sha(Path(__file__).with_name(name)) for name in
                                [Path(__file__).name, 'triangle_correspondence_bound.py', 'verify_triangle_correspondence_bound.py']}}
    out = args.source / '02-保存对象全量复审与有界几何对应.json'
    assert not out.exists()

    def save():
        temporary = out.with_suffix('.tmp')
        temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        temporary.replace(out)

    save()
    for entry in original['rows']:
        for pair in entry['pairs']:
            repeat = pair['repeat']
            paths = [args.source / entry['case'] / f'repeat{repeat}_{mode}.npz' for mode in (0, 1)]
            meshes, checks = [], []
            for path in paths:
                data = np.load(path)
                v, f, bits = (data[name] for name in ('vertices', 'faces', 'bits'))
                meshes.append((v, f, bits))
                checks.append(full.audit(v, f) if len(f) else {'empty_result': True, 'faces': 0})
            # 保存对象的几何结论逐字段核对，重测耗时另存，不要求运行耗时相等。
            keys = ('parsed', 'topology_valid', 'vertices', 'faces', 'closed', 'self_intersection_pairs',
                    'embedded_closed', 'exact_degenerate_faces', 'kernel', 'empty_result')
            assert all(all(checks[mode].get(key) == pair['checks'][label].get(key) for key in keys)
                       for mode, label in enumerate(('False', 'True')))
            report['rows'].append({'case': entry['case'], 'repeat': repeat, 'output_sha256': [sha(path) for path in paths],
                                   'saved_audits_identical_to_run': True, 'checks': checks,
                                   'correspondence': certify_with_virtual_snap(*meshes[0], *meshes[1])})
        save()
    report['correspondence_proved'] = sum(row['correspondence']['accepted'] for row in report['rows'])
    report['saved_objects'] = len(report['rows']) * 2
    report['exactly_embedded_objects'] = sum(check.get('embedded_closed', False) for row in report['rows'] for check in row['checks'])
    report['nonempty_returned_objects'] = sum(not check.get('empty_result', False) for row in report['rows'] for check in row['checks'])
    report['max_proved_error_upper_mm'] = max((row['correspondence'].get('error_upper_mm', 0) for row in report['rows']
                                             if row['correspondence']['accepted']), default=0)
    report['timings'] = {}
    for label, selected in [('all', original['rows']), ('ct', original['rows'][11:])]:
        pairs = [pair for entry in selected for pair in entry['pairs'] if not pair['warmup']]
        values = {key: np.array([pair['timings'][key]['boolean_ms'] for pair in pairs]) for key in ('False', 'True')}
        report['timings'][label] = {'pairs': len(pairs), 'median_ms': {key: float(np.median(value)) for key, value in values.items()},
                                  'mean_ms': {key: float(np.mean(value)) for key, value in values.items()},
                                  'paired_median_difference_ms': float(np.median(values['True']-values['False'])),
                                  'faster_pairs': int(np.sum(values['True'] < values['False']))}
    report['status'] = 'completed'
    save()
    print(json.dumps({key: report[key] for key in ('status', 'saved_objects', 'correspondence_proved', 'timings')}), flush=True)


if __name__ == '__main__':
    main()
