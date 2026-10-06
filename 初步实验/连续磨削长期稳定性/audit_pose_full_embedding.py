"""绑定每张保存对象的全量CGAL精确自交核查，保留所有拒绝和执行失败。"""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time
import numpy as np
import pyvista as pv
from timed_paths import beijing_now, digest


def vertex_manifold_closed(faces):
    """沿用项目顶点链接单环定义，额外核查顶点处的非流形拼接。"""
    links = {}
    for a, b, c in faces:
        for center, first, second in ((a, b, c), (b, c, a), (c, a, b)):
            ring = links.setdefault(int(center), {})
            ring.setdefault(int(first), set()).add(int(second))
            ring.setdefault(int(second), set()).add(int(first))
    for ring in links.values():
        if not ring or any(len(neighbors) != 2 for neighbors in ring.values()):
            return False
        visited = {next(iter(ring))}
        frontier = list(visited)
        while frontier:
            for neighbor in ring[frontier.pop()] - visited:
                visited.add(neighbor)
                frontier.append(neighbor)
        if len(visited) != len(ring):
            return False
    return True


def obj_bytes(vertices, faces):
    return (''.join(f'v {x:.17g} {y:.17g} {z:.17g}\n' for x, y, z in vertices)
            + ''.join(f'f {a+1} {b+1} {c+1}\n' for a, b, c in faces)).encode('ascii')


def parsed_roundtrip(text, vertices, faces):
    lines = text.decode('ascii').splitlines()
    points = np.array([[float(x) for x in line.split()[1:]] for line in lines if line.startswith('v ')])
    triangles = np.array([[int(x) - 1 for x in line.split()[1:]] for line in lines if line.startswith('f ')])
    return bool(np.array_equal(points, vertices) and np.array_equal(triangles, faces))


def checker(executable, file):
    start = time.perf_counter()
    process = subprocess.run([str(executable), str(file)], capture_output=True, text=True, encoding='utf-8', errors='replace')
    result = {'returncode': process.returncode, 'stdout': process.stdout, 'stderr': process.stderr,
              'elapsed_seconds_observation': time.perf_counter() - start}
    try:
        result['certificate'] = json.loads(process.stdout) if process.returncode == 0 else None
    except json.JSONDecodeError:
        result['certificate'] = None
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--executable', type=Path, required=True)
    parser.add_argument('--cpp-source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    geometry = args.output / '实际17位OBJ'
    geometry.mkdir()
    shutil.copyfile(__file__, args.output / '实际复审源码.py')
    shutil.copyfile(args.cpp_source, args.output / '实际精确检查器源码.cpp')
    attempts = []
    for folder in sorted(args.input.glob('路线[0-9][0-9]')):
        plan = json.loads((folder / '01-实际执行输入与方法绑定.json').read_text(encoding='utf-8'))
        record = json.loads((folder / '03-实际四方法完整记录.json').read_text(encoding='utf-8'))
        if record['status'] != 'complete' or len(record['attempts']) != 40:
            raise ValueError('路线尚未完整终态')
        for attempt in record['attempts']:
            if attempt['status'] != 'saved_and_reviewed':
                raise ValueError('实际320保存对象前提不成立')
            attempts.append(dict(attempt, route=folder.name, body=plan['body']))
    if len(attempts) != 320:
        raise ValueError('计划保存对象分母应为320')
    binding = {'created_at_beijing': beijing_now(), 'planned_saved_objects': 320,
               'source_sha256': digest(__file__), 'cpp_source_sha256': digest(args.cpp_source),
               'executable': str(args.executable), 'executable_sha256': digest(args.executable),
               'inputs': [{'file': x['file'], 'sha256': x['sha256']} for x in attempts],
               'scope': '保存二进制64网格完整自交与顶点链接核查；不是材料正确性或几何误差证书'}
    (args.output / '01-全量精确核查运行前绑定.json').write_text(json.dumps(binding, ensure_ascii=False, indent=2), encoding='utf-8')
    controls = []
    base = pv.Box(bounds=(-1, 1, -1, 1, -1, 1)).triangulate()
    # 控制几何先转为FP64，避免2^-40间隙被默认FP32坐标量化为接触。
    base.points = np.asarray(base.points, dtype=np.float64)
    near = base.copy()
    near.points[:, 0] += 2 + 2 ** -40
    touching = base.copy()
    touching.points[:, 0] += 2
    overlap = base.copy()
    overlap.points[:, 0] += .5
    far = base.copy()
    far.points[:, 0] += 4
    open_mesh = pv.PolyData(base.points, base.faces.reshape(-1, 4)[1:].ravel())
    # 六项有限几何控制先校准同一可执行文件，失败时不运行评价网格。
    for name, poly, expected in [('闭盒', base, True), ('分离双盒', base.merge(far, merge_points=False), True),
                                 ('重叠双盒', base.merge(overlap, merge_points=False), False), ('开口盒', open_mesh, False),
                                 ('近距分离双盒', base.merge(near, merge_points=False), True),
                                 ('接触双盒', base.merge(touching, merge_points=False), False)]:
        file = geometry / f'控制_{name}.obj'
        file.write_bytes(obj_bytes(poly.points, poly.faces.reshape(-1, 4)[:, 1:]))
        actual = checker(args.executable, file)
        certificate = actual['certificate'] or {}
        matched = actual['returncode'] == 0 and certificate.get('embedded_closed') == expected
        controls.append({'name': name, 'expected_embedded_closed': expected, 'matched': matched, 'result': actual})
    (args.output / '02-实际检查器六项几何控制.json').write_text(json.dumps({'updated_at_beijing': beijing_now(), 'controls': controls}, ensure_ascii=False, indent=2), encoding='utf-8')
    if not all(x['matched'] for x in controls):
        raise ValueError('检查器有限控制未通过，不能登记评价证书')
    rows, cache = [], {}
    with (args.output / '03-逐保存对象实际核查.jsonl').open('x', encoding='utf-8') as events:
        for index, attempt in enumerate(attempts):
            file = Path(attempt['file'])
            if digest(file) != attempt['sha256']:
                raise ValueError('保存对象摘要变化')
            poly = pv.read(file)
            vertices, faces = np.asarray(poly.points), poly.faces.reshape(-1, 4)[:, 1:]
            text = obj_bytes(vertices, faces)
            sha = hashlib.sha256(text).hexdigest()
            obj = geometry / f'{sha}.obj'
            if sha not in cache:
                if not parsed_roundtrip(text, vertices, faces):
                    raise ValueError('17位OBJ未逐位恢复保存对象')
                obj.write_bytes(text)
                actual = checker(args.executable, obj)
                cache[sha] = {'first_object_index': index, 'result': actual, 'vertex_manifold_closed': vertex_manifold_closed(faces)}
            cached = cache[sha]
            certificate = cached['result']['certificate'] or {}
            counts_match = certificate.get('vertices') == len(vertices) and certificate.get('faces') == len(faces)
            embedded = cached['result']['returncode'] == 0 and certificate.get('embedded_closed', False) and counts_match
            basic = attempt['metrics']
            eligible = bool(embedded and cached['vertex_manifold_closed'] and basic['finite_vertices']
                            and basic['physical_degenerate_faces'] == 0 and basic['watertight'] and basic['winding_consistent']
                            and basic['components'] == (2 if attempt['body'] == 'gap' else 1))
            row = {'route': attempt['route'], 'body': attempt['body'], 'method': attempt['method'], 'event': attempt['material_version'],
                   'saved_file': str(file), 'saved_sha256': attempt['sha256'], 'obj_sha256': sha,
                   'first_identical_geometry_object_index': cached['first_object_index'], 'exact_result': cached['result'],
                   'vertex_manifold_closed': cached['vertex_manifold_closed'], 'full_exact_embedding_bound': bool(embedded),
                   'original_float_alarm_faces': basic['self_intersection_alarm_faces'],
                   'original_basic_display_eligible': attempt['basic_display_eligible'], 'full_exact_basic_display_eligible': eligible}
            rows.append(row)
            events.write(json.dumps(row, ensure_ascii=False) + '\n')
            events.flush()
            if (index + 1) % 40 == 0:
                print(json.dumps({'saved_objects': index + 1, 'planned': 320, 'unique_geometry_executions': len(cache)}, ensure_ascii=False), flush=True)
                (args.output / '04-全量核查状态.json').write_text(json.dumps({'status': 'running', 'updated_at_beijing': beijing_now(), 'reviewed': len(rows), 'planned': 320}, ensure_ascii=False), encoding='utf-8')
    if digest(args.executable) != binding['executable_sha256'] or digest(args.cpp_source) != binding['cpp_source_sha256']:
        raise ValueError('实际执行检查器发生变化')
    totals = defaultdict(lambda: {'saved': 0, 'embedded': 0, 'original_eligible': 0, 'exact_eligible': 0, 'float_alarm_outputs': 0, 'exact_intersecting_outputs': 0})
    for row in rows:
        item = totals[row['method']]
        item['saved'] += 1
        item['embedded'] += row['full_exact_embedding_bound']
        item['original_eligible'] += row['original_basic_display_eligible']
        item['exact_eligible'] += row['full_exact_basic_display_eligible']
        item['float_alarm_outputs'] += row['original_float_alarm_faces'] > 0
        item['exact_intersecting_outputs'] += (row['exact_result']['certificate'] or {}).get('self_intersection_pairs', 0) > 0
    result = {'status': 'complete', 'updated_at_beijing': beijing_now(), 'reviewed': len(rows), 'planned': 320,
              'unique_geometry_executions': len(cache), 'totals': dict(totals), 'ledger_sha256': digest(args.output / '03-逐保存对象实际核查.jsonl'),
              'scope': binding['scope']}
    (args.output / '04-全量核查状态.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
