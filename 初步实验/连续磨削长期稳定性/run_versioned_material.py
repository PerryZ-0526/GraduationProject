"""材料与诊断显示分开记账；仅支持明确检查点边界的受控进程恢复。"""
import argparse
import json
import os
from pathlib import Path
import shutil
import numpy as np
import pyvista as pv
import trimesh
from material_state import MaterialState
from conditioned_extraction import extract
from timed_paths import beijing_now, digest


def atomic_json(path, value):
    temporary = path.with_suffix('.tmp')
    with temporary.open('w', encoding='utf-8') as output:
        json.dump(value, output, ensure_ascii=False, indent=2)
        output.flush()
        os.fsync(output.fileno())
    os.replace(temporary, path)


def display_audit(poly, body):
    mesh = trimesh.Trimesh(poly.points, poly.faces.reshape(-1, 4)[:, 1:], process=False)
    areas = mesh.area_faces
    valid = areas > 1e-12
    count = len(areas)
    finite = bool(np.isfinite(mesh.vertices).all())
    components = len(trimesh.graph.connected_components(mesh.face_adjacency, nodes=np.arange(count)))
    passed = finite and bool(valid.all()) and mesh.is_watertight and mesh.is_winding_consistent and components == (2 if body == 'gap' else 1)
    # 基础显示检查不含完整自交或材料几何证书，不能冒称正式输出验收。
    angles = np.degrees(mesh.face_angles.min(axis=1))
    return {'basic_display_eligible': bool(passed), 'finite': finite, 'faces': count,
            'physical_degenerate_faces': int(np.count_nonzero(~valid)),
            'watertight': bool(mesh.is_watertight), 'winding_consistent': bool(mesh.is_winding_consistent),
            'components': components, 'exact_embedding_certificate': False, 'material_geometry_certificate': False,
            'angle_tails': {str(t): {'valid_small_face_fraction_of_all': float(np.count_nonzero(valid & (angles < t)) / count),
                                   'valid_small_area_fraction': float(areas[valid & (angles < t)].sum() / areas[valid].sum())}
                            for t in (10, 5, 1)}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--trajectory', type=Path, required=True)
    parser.add_argument('--body', choices=('thin_wall', 'gap'), required=True)
    parser.add_argument('--zero', action='store_true')
    parser.add_argument('--stop', type=int, required=True)
    parser.add_argument('--display-every', type=int, default=100)
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    trajectory = np.load(args.trajectory)
    centers, times = trajectory['centers_mm'], trajectory['times_s']
    total = len(times) - 1
    if args.display_every <= 0 or not 0 < args.stop <= total or args.stop % args.display_every:
        raise ValueError('当前受控阶段必须停在明确显示/检查点边界')
    config = {'trajectory': str(args.trajectory), 'trajectory_sha256': digest(args.trajectory),
              'body': args.body, 'spacing_mm': .06, 'canonical_zero': args.zero, 'radius_mm': .4,
              'planned_events': total, 'display_every_events': args.display_every}
    plan_path = args.output / '01-运行前固定输入与方法.json'
    if not args.resume:
        args.output.mkdir(parents=True, exist_ok=False)
        frozen = args.output / '运行前冻结源码'
        frozen.mkdir()
        methods = []
        for name in ('run_versioned_material.py', 'material_state.py', 'conditioned_extraction.py', 'timed_paths.py'):
            shutil.copyfile(Path(__file__).parent / name, frozen / name)
            methods.append({'file': name, 'sha256': digest(frozen / name)})
        atomic_json(plan_path, {'created_at_beijing': beijing_now(), 'config': config, 'methods': methods,
                                'scope': f'离线带时间回放；每{args.display_every}事件基础显示检查，不是正式几何验收'})
        # 接收账本先写全，再执行材料；基础显示失败不能删除未处理事件。
        with (args.output / '02-完整接收事件.jsonl').open('x', encoding='utf-8') as received:
            for index in range(total):
                received.write(json.dumps({'event': index + 1, 'time_s': float(times[index + 1]),
                                           'start_mm': centers[index].tolist(), 'end_mm': centers[index + 1].tolist()}) + '\n')
            received.flush()
            os.fsync(received.fileno())
        state = MaterialState(args.body, .06)
        start, display_version = 0, None
        displays = []
    else:
        plan = json.loads(plan_path.read_text(encoding='utf-8'))
        if plan['config'] != config:
            raise ValueError('恢复配置与原输入身份不一致')
        for item in plan['methods']:
            if digest(args.output / '运行前冻结源码' / item['file']) != item['sha256']:
                raise ValueError('冻结源码变化')
        if digest(__file__) != next(item['sha256'] for item in plan['methods'] if item['file'] == Path(__file__).name):
            raise ValueError('恢复必须使用相同入口源码')
        checkpoint = json.loads((args.output / '05-检查点指针.json').read_text(encoding='utf-8'))
        if digest(args.output / '02-完整接收事件.jsonl') != checkpoint['received_sha256']:
            raise ValueError('恢复接收事件账本摘要变化')
        checkpoint_file = args.output / checkpoint['file']
        if digest(checkpoint_file) != checkpoint['sha256']:
            raise ValueError('材料检查点摘要变化')
        prior = json.loads((args.output / '06-状态记录.json').read_text(encoding='utf-8'))
        start = checkpoint['material_version']
        if prior['material_version'] != start or start >= args.stop:
            raise ValueError('不是可恢复的明确阶段边界')
        # 本版只恢复完整检查点边界；任意中途故障尾部尚未实现，不伪造恢复证据。
        applied = (args.output / '03-实际材料事件.jsonl').read_text(encoding='utf-8').splitlines()
        if len(applied) != start or [json.loads(line)['event'] for line in applied] != list(range(1, start + 1)):
            raise ValueError('实际事件尾部与检查点不一致，禁止本版自动恢复')
        state = MaterialState(args.body, .06)
        saved = np.load(checkpoint_file)
        if not np.array_equal(state.axis, saved['axis_mm']):
            raise ValueError('检查点网格坐标变化')
        state.field[:] = saved['field']
        display_version, displays = prior['display_version'], prior['display_attempts']
        if any(digest(args.output / item['file']) != item['sha256'] for item in displays):
            raise ValueError('恢复前已保存显示对象摘要变化')
    with (args.output / '03-实际材料事件.jsonl').open('a', encoding='utf-8') as applied:
        for index in range(start, args.stop):
            event = index + 1
            change = state.apply(centers[index], centers[index + 1], .4)
            applied.write(json.dumps(dict(change, event=event, time_s=float(times[event]),
                                          recorded_at_beijing=beijing_now())) + '\n')
            applied.flush()
            os.fsync(applied.fileno())
            if event % args.display_every == 0:
                poly, method = extract(state.field, state.axis, True, args.zero)
                mesh_path = args.output / f'显示尝试_{event:04d}.vtp'
                poly.save(mesh_path)
                actual = pv.read(mesh_path)
                audit = display_audit(actual, args.body)
                if audit['basic_display_eligible']:
                    display_version = event
                displays.append({'material_version': event, 'time_s': float(times[event]),
                                 'file': mesh_path.name, 'sha256': digest(mesh_path), 'method': method, 'audit': audit,
                                 'display_version_after': display_version,
                                 'display_age_events': None if display_version is None else event - display_version,
                                 'display_age_path_seconds': None if display_version is None else float(times[event] - times[display_version])})
    field_path = args.output / f'材料检查点_{args.stop:04d}.npz'
    # 检查点先完整写盘，再原子替换指针；保留前一阶段文件和原事件账本。
    with field_path.open('xb') as output:
        np.savez(output, field=state.field, axis_mm=state.axis)
        output.flush()
        os.fsync(output.fileno())
    atomic_json(args.output / '05-检查点指针.json', {'material_version': args.stop, 'file': field_path.name,
                                                'sha256': digest(field_path), 'received_sha256': digest(args.output / '02-完整接收事件.jsonl')})
    record = {'updated_at_beijing': beijing_now(), 'status': 'complete' if args.stop == total else 'controlled_checkpoint',
              'material_version': args.stop, 'display_version': display_version, 'display_attempts': displays,
              'resumed_from_version': start, 'planned_events': total, 'field_finite': bool(np.isfinite(state.field).all()),
              'scope': '基础诊断显示；无完整自交、连续几何、实时调度或任意故障恢复证书'}
    atomic_json(args.output / '06-状态记录.json', record)
    atomic_json(args.output / f'阶段_{args.stop:04d}_状态快照.json', record)
    print(json.dumps({'body': args.body, 'zero': args.zero, 'material_version': args.stop,
                      'display_version': display_version, 'eligible_attempts': sum(x['audit']['basic_display_eligible'] for x in displays)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
