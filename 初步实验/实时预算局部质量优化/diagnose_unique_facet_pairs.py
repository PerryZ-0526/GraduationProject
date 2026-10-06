"""相同私有Geogram库交错开关排序省略，完整保存同源数组和精确审计。"""
import argparse
from pathlib import Path
import datetime
import hashlib
import json
import numpy as np
from geogram_memory import GeogramMemory
from exact_mesh_memory import ExactMeshMemory
from triangle_correspondence_bound import certify_correspondence


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(exist_ok=False)
    api = GeogramMemory()
    full = ExactMeshMemory()
    identity = json.loads(Path(__file__).with_name('build_identity.json').read_text(encoding='utf-8'))
    assert identity['status'] == 'completed'
    for row in identity['libraries']:
        assert sha(row['path']) == row['sha256']
    mapped = [line for line in Path('/proc/self/maps').read_text().splitlines() if 'libgeogram.so' in line]
    assert any(str(Path(identity['libraries'][0]['path']).resolve()) in line for line in mapped)
    directories = sorted(args.inputs.glob('case*'))
    assert len(directories) == 27
    report = {'time_beijing': datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
              'status': 'running', 'build_identity': identity, 'actual_maps': mapped, 'rows': [],
              'diagnostic_only': True, 'method_sha256': sha(__file__)}
    record = args.output / '01-唯一面扫描同源完整对照.json'

    def save():
        temporary = record.with_suffix('.tmp')
        temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        temporary.replace(record)

    save()
    try:
        for source in directories:
            path = source / 'inputs.npz'
            data = np.load(path)
            av, af, bv, bf = (data[key] for key in ('av', 'af', 'bv', 'bf'))
            ac, bc = full.audit(av, af), full.audit(bv, bf)
            assert ac['embedded_closed'] and bc['embedded_closed']
            folder = args.output / source.name
            folder.mkdir()
            np.savez(folder / 'inputs.npz', av=av, af=af, bv=bv, bf=bf)
            row = {'case': source.name, 'source_input_sha256': sha(path), 'input_a': ac, 'input_b': bc, 'pairs': []}
            report['rows'].append(row)
            for repeat in range(6):
                results, timings, checks = {}, {}, {}
                for enabled in ([False, True] if repeat % 2 == 0 else [True, False]):
                    v, f, bits, timing = api.difference(av, af, bv, bf, no_simplify=True,
                                                      certified_operands=True, linear_unique_facets=enabled)
                    results[enabled] = (v, f, bits)
                    timings[str(enabled)] = timing
                    checks[str(enabled)] = full.audit(v, f) if len(f) else {'empty_result': True, 'faces': 0}
                    np.savez(folder / f'repeat{repeat}_{int(enabled)}.npz', vertices=v, faces=f, bits=bits)
                # 差三角化按已验证的有向边界及距离上界核对，不把严格数组差异直接消失。
                correspondence = certify_correspondence(*results[False], *results[True])
                keys = ('topology_valid', 'closed', 'embedded_closed', 'self_intersection_pairs', 'exact_degenerate_faces')
                same_checks = all(checks['False'].get(key) == checks['True'].get(key) for key in keys)
                row['pairs'].append({'repeat': repeat, 'warmup': repeat == 0, 'timings': timings,
                                     'checks': checks, 'checks_identical': same_checks,
                                     'arrays_identical': all(np.array_equal(x, y) for x, y in zip(results[False], results[True])),
                                     'correspondence': correspondence})
                save()
            print(json.dumps({'case': source.name, 'complete_pairs': len(row['pairs']),
                              'last_boolean_ms': {key: value['boolean_ms'] for key, value in timings.items()}}), flush=True)
        pairs = [pair for row in report['rows'] for pair in row['pairs']]
        measured = [pair for pair in pairs if not pair['warmup']]
        report['pair_count'] = len(pairs)
        report['measurement_pairs'] = len(measured)
        report['all_checks_identical'] = all(pair['checks_identical'] for pair in pairs)
        report['all_correspondence_accepted'] = all(pair['correspondence']['accepted'] for pair in pairs)
        report['strict_array_difference_pairs'] = sum(not pair['arrays_identical'] for pair in pairs)
        report['boolean_median_ms'] = {key: float(np.median([pair['timings'][key]['boolean_ms'] for pair in measured]))
                                       for key in ('False', 'True')}
        report['status'] = 'completed'
        save()
        print(json.dumps({key: report[key] for key in ('status', 'pair_count', 'all_checks_identical',
                                                      'all_correspondence_accepted', 'boolean_median_ms')}), flush=True)
    except Exception as error:
        report['status'] = 'failed'
        report['error'] = repr(error)
        save()
        raise


if __name__ == '__main__':
    main()
