"""在同一实例比较基座增量参照与冻结旧核函数的完整前缀重放。"""
import argparse
import os
from pathlib import Path
import sys
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / '连续磨削实验基座'))
from event_store import atomic_json, digest, now, read_json, require_file


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--folder', type=Path, required=True)
    parser.add_argument('--route', required=True)
    parser.add_argument('--event', required=True)
    parser.add_argument('--port', type=int, required=True)
    parser.add_argument('--host', required=True)
    parser.add_argument('--legacy', type=Path)
    args = parser.parse_args()
    folder = args.folder.resolve()
    binding = read_json(folder / '01-运行绑定.json')['binding']
    prepared = Path(binding['prepared'])
    manifest = read_json(prepared / '01-完整范围冻结清单.json')
    route = next(route for route in manifest['routes'] if route['id'] == args.route)
    details = []
    with (folder / '02-事件索引.jsonl').open(encoding='utf-8') as stream:
        for line in stream:
            item = __import__('json').loads(line)
            if item['route'] == args.route and item['event'] == args.event:
                path = folder / item['record_file']
                if digest(path) != item['record_sha256']:
                    raise ValueError('事件审计摘要变化')
                details.append(read_json(path))
    if len(details) != 1:
        raise ValueError('要求完整提交且唯一的事件')
    reference = require_file(details[0]['state']['reference']['mesh'])
    snapshot = folder / 'method'
    sys.path.insert(0, str(snapshot))
    os.environ['GPU_SSH_HOST'] = args.host
    from legacy_adapter import LegacyBackend
    from run_constrained_feedback import global_geometry
    result_folder = folder / ('reference_equivalence_' + uuid.uuid4().hex[:12])
    backend = LegacyBackend(snapshot, result_folder, args.port)
    try:
        environment = backend.setup([])
        mesh, replay = backend.reference_step(prepared, route, args.event, result_folder / 'full_prefix')
        if mesh is None:
            raise ValueError('冻结完整前缀参照失败')
        output = result_folder / 'full_prefix' / 'validated_reference.obj'
        result = {'time_beijing': now(), 'route': args.route, 'event': args.event,
            'environment': environment, 'incremental_sha256': digest(reference), 'full_replay_sha256': digest(output),
            'byte_identical': digest(reference) == digest(output), 'full_replay': replay,
            'geometry': global_geometry(backend.load_mesh(reference), mesh),
            'scope': '同冻结修复核的增量执行与完整前缀重放等价性，非独立几何真值'}
        if args.legacy:
            old = args.legacy / (args.route + '_' + args.event + '_reference') / 'reference.obj'
            if old.exists():
                result['old_primary_reference_geometry'] = global_geometry(backend.load_mesh(reference), backend.load_mesh(old))
        atomic_json(result_folder / '02-增量与完整前缀参照对照.json', result)
        print('byte_identical', result['byte_identical'], 'full_booleans', len(replay['runs']),
              'geometry_probe', result['geometry']['probe_max_mm'], flush=True)
        if not result['byte_identical']:
            raise ValueError('增量与冻结完整前缀参照未达到逐字节一致，须先调查')
    finally:
        backend.close()


if __name__ == '__main__':
    main()
