"""保存原24步前缀并逐层加深，准备只统计几何偏差的连续开发输入。"""
import argparse
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sys

BASE = Path(__file__).resolve().parents[1] / 'Geogram与PaMO组合验证'
sys.path[:0] = [str(BASE), str(BASE.parent / '共同运动记录与方法对照')]
from freeze_followup_inputs import capsule_mesh
from motion_record import replay_case


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    manifest_path = args.source / '01-完整范围冻结清单.json'
    original = json.loads(manifest_path.read_text(encoding='utf-8'))
    args.output.mkdir(parents=True, exist_ok=False)
    inputs = args.output / 'inputs'
    inputs.mkdir()
    routes = []
    for old in original['routes']:
        if old['split'] != 'long':
            continue
        route = deepcopy(old)
        route['id'] = old['id'].replace('_24', '_384')
        route['scope'] = '已见开发输入，原24步前缀保持；16层加深，不称独立评价或临床路径'
        # 第一层保留原事件与工具字节，之后每层加深0.03毫米并重新生成扫掠工具。
        events = deepcopy(old['events'])
        for layer in range(1, 16):
            for local_index, template in enumerate(old['events']):
                event = deepcopy(template)
                index = len(events)
                event.update(id=f'e{index}', arrival_index=index, timestamp_ms=index * 100,
                             connect_from_previous=local_index > 0)
                event['position_mm'][2] -= layer * 0.03
                events.append(event)
        route['events'] = events
        route['cutting_prefix_ids'] = [event['id'] for event in events]
        route['prefix_tools'] = deepcopy(old['prefix_tools'])
        for item in [{'mesh': old['initial_mesh'], 'sha256': old['initial_mesh_sha256']}, *old['prefix_tools']]:
            source = args.source / 'inputs' / item['mesh']
            if digest(source) != item['sha256']:
                raise ValueError('原输入摘要变化')
            shutil.copyfile(source, inputs / item['mesh'])
        primitives = replay_case(route, original['replay_policy'])['primitives']
        if len(primitives) != 384:
            raise ValueError('生成的扫掠事件数不符')
        for primitive in primitives[24:]:
            name = route['id'] + '_' + primitive['event_id'] + '_tool.obj'
            capsule_mesh(primitive).export(inputs / name, digits=17)
            route['prefix_tools'].append({'event_id': primitive['event_id'], 'mesh': name,
                                          'sha256': digest(inputs / name)})
        routes.append(route)
    if len(routes) != 2:
        raise ValueError('必须保留原两条长路线')
    record = {'time_beijing': datetime.now(timezone(timedelta(hours=8))).isoformat(),
              'generator_sha256': digest(__file__), 'source_manifest_sha256': digest(manifest_path),
              'routes': routes, 'replay_policy': original['replay_policy'],
              'geometry_policy': 'report_only_no_distance_stop',
              'planned_events': 768, 'planned_feedback_branches': ['full', 'candidate'],
              'actual_gpu_events': 0, 'scope': '准备资产；实际去除、偏差和运行长度须由完整反馈取得'}
    (args.output / '01-完整范围冻结清单.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
    # 冻结实际新入口及顶层依赖源码，不修改任何历史实验副本。
    frozen = args.output / '冻结方法'
    for folder in [BASE, BASE.parent / '共同运动记录与方法对照']:
        destination = frozen / folder.name
        destination.mkdir(parents=True)
        for source in folder.glob('*.py'):
            if not source.name.startswith('test_'):
                shutil.copyfile(source, destination / source.name)
    shutil.copyfile(__file__, args.output / Path(__file__).name)
    print(json.dumps({'routes': 2, 'events': 768, 'actual_gpu_events': 0}, ensure_ascii=False))


if __name__ == '__main__':
    main()
