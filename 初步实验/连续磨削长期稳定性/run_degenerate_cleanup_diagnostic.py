"""复用真实拒绝输入，执行局部清理、完整精确复审和实际GPU质量处理。"""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys

BASE = Path(__file__).resolve().parents[1] / '连续磨削实验基座'
sys.path.insert(0, str(BASE))
from event_store import atomic_json, digest, file_identity, now, read_json, require_file


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prior', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--route', required=True)
    parser.add_argument('--event', required=True)
    parser.add_argument('--host', required=True)
    parser.add_argument('--port', type=int, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    snapshot = args.prior / 'method'
    sys.path.insert(0, str(snapshot))
    os.environ['GPU_SSH_HOST'] = args.host
    from legacy_adapter import LegacyBackend
    from degenerate_cleanup import repair_before_reject
    from run_constrained_feedback import global_geometry
    binding = read_json(args.prior / '01-运行绑定.json')['binding']
    prepared = Path(binding['prepared'])
    route = next(route for route in read_json(prepared / '01-完整范围冻结清单.json')['routes'] if route['id'] == args.route)
    rows = []
    for line in (args.prior / '02-事件索引.jsonl').read_text(encoding='utf-8').splitlines():
        item = json.loads(line)
        if item['route'] == args.route and item['event'] == args.event:
            record_path = args.prior / item['record_file']
            if digest(record_path) != item['record_sha256']:
                raise ValueError('实际失败记录摘要变化')
            detail = read_json(record_path)
            rows.append(next(row for row in detail['rows'] if row['branch'] == 'candidate'))
    if len(rows) != 1 or rows[0]['status'] != 'maintenance_input_invalid':
        raise ValueError('没有唯一的实际退化输入拒绝记录')
    sources = list(args.prior.glob('attempts/*/' + args.route + '_' + args.event + '_candidate/input/clean_source.obj'))
    if len(sources) != 1:
        raise ValueError('实际拒绝输入文件身份不唯一')
    source, labels = sources[0], sources[0].with_name('clean_labels.json')
    tool = prepared / 'inputs' / next(tool['mesh'] for tool in route['prefix_tools'] if tool['event_id'] == args.event)
    (args.output / 'base').mkdir()
    for path in BASE.glob('*.py'):
        shutil.copyfile(path, args.output / 'base' / path.name)
    report = {'time_beijing': now(), 'status': 'running', 'prior_record': file_identity(record_path),
        'source': file_identity(source), 'labels': file_identity(labels), 'tool': file_identity(tool),
        'original_status': rows[0]['status'], 'core_sources': {path.name: digest(path) for path in BASE.glob('*.py')},
        'method_sources': binding['methods'], 'scope': '实际拒绝输入的隔离修复及完整GPU处理，不算连续发布'}
    atomic_json(args.output / '01-退化输入隔离清理与GPU复审.json', report)
    backend = LegacyBackend(snapshot, args.output / 'engine', args.port)
    try:
        report['environment'] = backend.setup([])
        bits = read_json(labels)['operand_bits']
        repaired, repaired_bits, repair = repair_before_reject(backend.load_mesh(source), bits, backend.validate, args.output / 'cleanup')
        report['cleanup'] = repair
        atomic_json(args.output / '01-退化输入隔离清理与GPU复审.json', report)
        print('cleanup', repair['accepted'], 'remaining', repair['remaining_invalid_faces'],
              'full_embedding', repair['validated_metrics'].get('full_exact_embedding_bound'), flush=True)
        if repair['accepted']:
            repaired_path = args.output / 'cleanup/repaired_source.obj'
            repaired_labels = args.output / 'cleanup/repaired_labels.json'
            report['quality_attempts'] = []
            for method in ('boolean', 'expanded'):
                destination = args.output / ('quality_' + method)
                attempt = backend.quality.run(repaired_path, repaired_labels, tool, method, destination)
                attempt = backend.quality.audit(repaired_path, repaired_labels, tool, destination, attempt)
                if attempt['status'] == 'accepted_sampled':
                    reference = require_file(detail['state']['reference']['mesh'])
                    attempt['cumulative_geometry'] = global_geometry(backend.load_mesh(destination / 'candidate.obj'), backend.load_mesh(reference))
                report['quality_attempts'].append(attempt)
                atomic_json(args.output / '01-退化输入隔离清理与GPU复审.json', report)
                print('quality', method, attempt['status'], flush=True)
                if attempt['status'] == 'accepted_sampled':
                    break
        report.update(status='completed', finished_beijing=now())
        atomic_json(args.output / '01-退化输入隔离清理与GPU复审.json', report)
    except BaseException as error:
        report.update(status='interrupted', error_type=type(error).__name__, error=str(error))
        atomic_json(args.output / '01-退化输入隔离清理与GPU复审.json', report)
        raise
    finally:
        backend.close()


if __name__ == '__main__':
    main()
