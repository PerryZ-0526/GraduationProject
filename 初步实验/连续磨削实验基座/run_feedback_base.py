"""连续磨削实验基座：独立增量参照、可替换质量处理和持久父链。"""
import argparse
import copy
import hashlib
import os
from pathlib import Path
import shutil
import sys
from time import perf_counter
import uuid
from event_store import EventStore, atomic_json, digest, encoded, file_identity, now, read_json, require_file
from prefix_reference import PrefixReference, prefix_hash


def snapshot_method(output, method_dir, legacy_run, quality_plugin):
    snapshot = output / 'method'
    snapshot.mkdir(parents=True, exist_ok=False)
    for path in sorted(Path(method_dir).iterdir()):
        if path.is_file() and path.suffix in ('.py', '.cpp') and not path.name.startswith('test_'):
            shutil.copyfile(path, snapshot / path.name)
    for name in ('preserved_reference.py', 'preserved_controller.py', 'physical_feedback_entry.py'):
        shutil.copyfile(Path(legacy_run) / name, snapshot / name)
    if quality_plugin:
        shutil.copyfile(quality_plugin, snapshot / 'base_quality_plugin.py')
    common = Path(method_dir).parent / '共同运动记录与方法对照'
    if not common.is_dir():
        raise FileNotFoundError('冻结的共同审计依赖缺失：' + str(common))
    shutil.copytree(common, output / common.name, ignore=shutil.ignore_patterns('__pycache__'))
    return snapshot


def binding_for(snapshot, prepared, split, routes, branches):
    return {'schema': 1, 'prepared': str(prepared.resolve()), 'manifest_sha256': digest(prepared / '01-完整范围冻结清单.json'),
        'split': split, 'plans': {route['id']: route['cutting_prefix_ids'] for route in routes},
        'branches': branches,
        'methods': {path.name: digest(path) for path in sorted(snapshot.iterdir()) if path.is_file()},
        'shared_audit_sources': {path.name: digest(path) for path in sorted((snapshot.parent / '共同运动记录与方法对照').glob('*.py'))},
        'base_sources': {path.name: digest(path) for path in sorted(Path(__file__).parent.glob('*.py'))},
        'geometry_policy': 'report_only_no_distance_stop',
        'reference': 'verified_independent_prefix_same_legacy_repair_and_checker'}


def check_state(state):
    for parent in state['parents'].values():
        require_file(parent)
    if state.get('reference'):
        require_file(state['reference']['mesh'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepared', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--method-dir', type=Path)
    parser.add_argument('--legacy-run', type=Path)
    parser.add_argument('--quality-plugin', type=Path)
    parser.add_argument('--port', type=int, required=True)
    parser.add_argument('--host', required=True)
    parser.add_argument('--split', choices=('development', 'evaluation', 'long', 'application'), default='long')
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--events-per-run', type=int)
    parser.add_argument('--candidate-only', action='store_true')
    parser.add_argument('--fork-from', type=Path)
    parser.add_argument('--fork-before', help='从旧批次指定路线和事件之前分叉，格式为路线:事件')
    args = parser.parse_args()
    if args.events_per_run is not None and args.events_per_run < 1:
        raise ValueError('本次提交数量必须为正数')
    args.output, args.prepared = args.output.resolve(), args.prepared.resolve()
    manifest = read_json(args.prepared / '01-完整范围冻结清单.json')
    routes = [route for route in manifest['routes'] if route['split'] == args.split]
    if not routes:
        raise ValueError('没有符合批次身份的路线')
    for route in routes:
        if len(set(route['cutting_prefix_ids'])) != len(route['cutting_prefix_ids']):
            raise ValueError('切削事件编号重复')
        for name, expected in [(route['initial_mesh'], route['initial_mesh_sha256']),
                               *[(tool['mesh'], tool['sha256']) for tool in route['prefix_tools']]]:
            require_file({'path': str(args.prepared / 'inputs' / name), 'sha256': expected})
    if args.resume:
        snapshot = args.output / 'method'
    else:
        if args.output.exists():
            raise FileExistsError(args.output)
        if not args.method_dir or not args.legacy_run:
            raise ValueError('首次运行须提供冻结方法目录和实际旧执行副本')
        # 方法先准备在同级临时目录，再交由账本创建最终目录。
        staging = args.output.with_name(args.output.name + '.prepare-' + uuid.uuid4().hex)
        snapshot = snapshot_method(staging, args.method_dir, args.legacy_run, args.quality_plugin)
    branches = ['candidate'] if args.candidate_only else ['full', 'candidate']
    binding = binding_for(snapshot, args.prepared, args.split, routes, branches)
    if args.resume:
        old_binding = read_json(args.output / '01-运行绑定.json')['binding']
        if 'fork' in old_binding:
            binding['fork'] = old_binding['fork']
    elif args.fork_from or args.fork_before:
        if not args.fork_from or not args.fork_before:
            raise ValueError('分叉必须同时提供旧目录和事件边界')
        binding['fork'] = {'prior': str(args.fork_from.resolve()), 'before': args.fork_before,
                          'binding_sha256': digest(args.fork_from / '01-运行绑定.json'),
                          'scope': '旧已提交前缀原样引用，边界后使用新清理机制；非同方法完整初态复跑'}
    store = EventStore(args.output, binding, args.resume)
    if not args.resume:
        shutil.move(str(snapshot), str(args.output / 'method'))
        shutil.move(str(staging / '共同运动记录与方法对照'), str(args.output / '共同运动记录与方法对照'))
        staging.rmdir()
        snapshot = args.output / 'method'
        # 封存实际执行的基座源码，以后接续可直接使用本批副本。
        (args.output / 'base').mkdir()
        for path in Path(__file__).parent.glob('*.py'):
            shutil.copyfile(path, args.output / 'base' / path.name)
    os.environ['GPU_SSH_HOST'] = args.host
    sys.path.insert(0, str(snapshot))
    backend = None
    processed = 0
    pending_path = args.output / '04-当前事件.json'
    pending = {}
    if pending_path.exists():
        envelope = read_json(pending_path)
        if hashlib.sha256(encoded(envelope['payload'])).hexdigest() != envelope['payload_sha256']:
            store.close()
            raise ValueError('未提交事件记录摘要变化')
        pending = envelope['payload']
    if pending.get('base_committed') != len(store.entries):
        pending = {}
    attempt_id = 'session_' + uuid.uuid4().hex[:12]
    attempt_folder = args.output / 'attempts' / attempt_id
    sessions = read_json(args.output / '06-连接尝试.json') if (args.output / '06-连接尝试.json').exists() else []
    try:
        from legacy_adapter import LegacyBackend
        from geometry_preservation_audit import replay_primitives
        from run_followup_geogram import contained
        if not args.resume and 'fork' in binding:
            fork = binding['fork']
            prior = Path(fork['prior'])
            prior_binding = read_json(prior / '01-运行绑定.json')['binding']
            if prior_binding['manifest_sha256'] != binding['manifest_sha256'] or prior_binding['methods'] != binding['methods']:
                raise ValueError('分叉输入或质量方法与旧批次不一致')
            fork_route, fork_event = fork['before'].rsplit(':', 1)
            plan = binding['plans'][fork_route]
            boundary = plan.index(fork_event)
            found = 0
            with (prior / '02-事件索引.jsonl').open(encoding='utf-8') as stream:
                for line in stream:
                    item = __import__('json').loads(line)
                    if item['route'] != fork_route:
                        continue
                    detail_path = prior / item['record_file']
                    if digest(detail_path) != item['record_sha256']:
                        raise ValueError('旧分叉记录摘要变化')
                    detail = read_json(detail_path)
                    if detail['event_index'] >= boundary:
                        break
                    if detail['event_index'] != found or detail['event'] != plan[found]:
                        raise ValueError('旧分叉前缀事件不连续')
                    imported_rows = [row for row in detail['rows'] if row['branch'] in ['R', *branches]]
                    if imported_rows[0]['status'] != 'reference_valid' or any(row['status'] not in
                        ('published_under_sampled_and_vertex_protocol', 'contained_reused_parent') for row in imported_rows[1:]):
                        raise ValueError('分叉边界前不是完整有效父链')
                    state = detail['state']
                    state['parents'] = {branch: state['parents'][branch] for branch in branches}
                    state['versions'] = {branch: state['versions'][branch] for branch in branches}
                    state['blocked'] = {branch: state['blocked'][branch] for branch in ['R', *branches]}
                    check_state(state)
                    store.commit(fork_route, detail['event'], found, imported_rows, state, detail['timings_ms'],
                        origin={'prior_record': file_identity(detail_path), 'prior_binding_sha256': fork['binding_sha256'],
                                'algorithm_epoch': '旧方法已提交前缀；不是新清理机制的新增发布'})
                    found += 1
            if found != boundary:
                raise ValueError('旧批次没有完整分叉前缀')
        backend = LegacyBackend(snapshot, attempt_folder, args.port,
                                snapshot / 'base_quality_plugin.py' if (snapshot / 'base_quality_plugin.py').exists() else None)
        prior_remotes = [session['remote'] for session in sessions]
        sessions.append({'time_beijing': now(), 'host': args.host, 'port': args.port,
                         'remote': backend.engine.remote, 'folder': str(attempt_folder)})
        atomic_json(args.output / '06-连接尝试.json', sessions)
        environment = backend.setup(prior_remotes)
        # 设备可以更换，材料与碰撞二进制摘要必须与首次环境一致。
        anchors = {key: environment[key] for key in ('provenance_binary_sha256', 'geogram_binary_sha256', 'checker_sha256')}
        anchors['author_extension'] = environment['device']['extension_sha256']
        anchor_path = args.output / '07-后端身份.json'
        if anchor_path.exists() and read_json(anchor_path) != anchors:
            raise ValueError('材料布尔、精确检查器或作者扩展变化')
        if not anchor_path.exists():
            atomic_json(anchor_path, anchors)
        store.status('running', planned_events=sum(len(route['cutting_prefix_ids']) for route in routes))
        for route in routes:
            rid = route['id']
            initial_path = args.prepared / 'inputs' / route['initial_mesh']
            initial = backend.load_mesh(initial_path)
            state = copy.deepcopy(store.states.get(rid))
            if state is None:
                valid, checks = backend.validate(initial, attempt_folder / (rid + '_initial_checks'), 'initial')
                atomic_json(attempt_folder / (rid + '_initial_audit.json'), checks)
                state = {'next_index': 0, 'parents': {branch: file_identity(initial_path) for branch in branches},
                    'versions': {branch: 0 for branch in branches}, 'blocked': {branch: not valid for branch in ['R', *branches]},
                    'retained': [], 'reference': None}
            check_state(state)
            tools = {tool['event_id']: tool for tool in route['prefix_tools']}
            events = {event['id']: event for event in route['events']}
            reference_engine = PrefixReference(backend, args.prepared, route, state['reference'])
            # 恢复时用原工具前缀重新计算身份链，拒绝过期或借用分支的参照游标。
            if state['reference']:
                expected = route['initial_mesh_sha256']
                for event in route['cutting_prefix_ids'][:state['reference']['next_index']]:
                    expected = prefix_hash(expected, event, tools[event]['sha256'])
                if expected != state['reference']['prefix_sha256']:
                    raise ValueError('独立参照工具前缀摘要变化')
            for index in range(state['next_index'], len(route['cutting_prefix_ids'])):
                event = route['cutting_prefix_ids'][index]
                started = perf_counter()
                primitive = replay_primitives(route, event)[-1]
                clip_radius = events[event].get('plan_clip_radius_mm')
                segments = [(item['start'], item['end']) for item in state['retained']
                            if item['radius'] == primitive['radius'] and item['clip_radius'] == clip_radius]
                reuse = contained(primitive['start'].tolist(), primitive['end'].tolist(), segments)
                tool = args.prepared / 'inputs' / tools[event]['mesh']
                rows, timings = [], {}
                reference = None
                recover_pending = pending.get('route') == rid and pending.get('event_index') == index
                if recover_pending and pending.get('rows'):
                    state, rows, timings = pending['state'], pending['rows'], pending['timings_ms']
                    check_state(state)
                    reference_engine.cursor = state['reference']
                    if state['reference'] and state['reference']['next_index'] == index + 1:
                        reference = backend.load_mesh(require_file(state['reference']['mesh']))
                def progress(phase):
                    store.pending({'status': 'executing', 'base_committed': len(store.entries), 'route': rid,
                        'event': event, 'event_index': index, 'phase': phase, 'attempt_id': attempt_id,
                        'rows': rows, 'state': state, 'timings_ms': timings})
                if not rows:
                    progress('reference_started')
                    folder = attempt_folder / (rid + '_' + event + '_reference')
                    if not state['blocked']['R']:
                        reference, record, cursor = reference_engine.advance(index, event, reuse, folder)
                        rows.append({'route': rid, 'event': event, 'branch': 'R',
                                     'status': 'reference_valid' if reference is not None else 'reference_rejected', 'recovery': record})
                        state['reference'] = cursor or state['reference']
                        state['blocked']['R'] = reference is None
                        timings['reference'] = record.get('reference_wall_ms', (perf_counter() - started) * 1000)
                    else:
                        rows.append({'route': rid, 'event': event, 'branch': 'R', 'status': 'blocked_by_previous_failure'})
                    progress('reference_saved')
                for branch in state['parents']:
                    if any(row['branch'] == branch for row in rows):
                        continue
                    progress(branch + '_started')
                    row = {'route': rid, 'event': event, 'branch': branch, 'published_version': state['versions'][branch]}
                    if state['blocked'][branch]:
                        row['status'] = 'blocked_by_previous_failure'
                    elif reuse:
                        row.update(status='contained_reused_parent', parent_sha256=state['parents'][branch]['sha256'],
                                   output_sha256=state['parents'][branch]['sha256'], state_mesh_version一致=True)
                    else:
                        parent = require_file(state['parents'][branch])
                        row, published = backend.run_branch(route, event, branch, parent, tool, initial, reference,
                            attempt_folder / (rid + '_' + event + '_' + branch))
                        if published:
                            state['parents'][branch] = published
                            state['versions'][branch] += 1
                            row['state_mesh_version一致'] = True
                        else:
                            state['blocked'][branch] = True
                        row['published_version'] = state['versions'][branch]
                    rows.append(row)
                    timings[branch] = row.get('frame_wall_including_audit_ms', 0)
                    progress(branch + '_saved')
                    print(rid, event, branch, row['status'], flush=True)
                if not reuse:
                    state['retained'].append({'start': primitive['start'].tolist(), 'end': primitive['end'].tolist(),
                                              'radius': primitive['radius'], 'clip_radius': clip_radius})
                state['next_index'] = index + 1
                timings['event_wall_this_session'] = (perf_counter() - started) * 1000
                commit_started = perf_counter()
                store.commit(rid, event, index, rows, state, timings)
                # 单独记录提交开销，不为更新一个计时数字重写已封存事件。
                print('COMMIT', rid, event, len(store.entries), 'write_ms', round((perf_counter() - commit_started) * 1000, 3), flush=True)
                pending = {}
                processed += 1
                if args.events_per_run and processed >= args.events_per_run:
                    store.status('paused_at_requested_checkpoint', requested_events_this_session=args.events_per_run)
                    return
        store.status('completed_with_recorded_failures', planned_events=sum(len(route['cutting_prefix_ids']) for route in routes))
    except BaseException as error:
        store.status('interrupted', exception_type=type(error).__name__, error=str(error),
                     algorithm_terminal=False, planned_events=sum(len(route['cutting_prefix_ids']) for route in routes))
        raise
    finally:
        if backend is not None:
            backend.close()
        store.close()


if __name__ == '__main__':
    main()
