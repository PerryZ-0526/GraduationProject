"""冻结同源提取消融；重读输出统计几何、拓扑与质量，保留所有负例。"""
import argparse
import json
from pathlib import Path
import shutil
import numpy as np
import pymeshlab
import pyvista as pv
import trimesh
from conditioned_extraction import extract
from material_state import initial_field, capsule_field
from timed_paths import beijing_now, digest


def metrics(poly):
    mesh = trimesh.Trimesh(poly.points, poly.faces.reshape(-1, 4)[:, 1:], process=False)
    areas = mesh.area_faces
    valid = areas > 1e-12
    angles = np.degrees(mesh.face_angles.min(axis=1))
    # 所有方法均调用相同浮点报警器；报警不是完整精确自交证书。
    detector = pymeshlab.MeshSet()
    detector.add_mesh(pymeshlab.Mesh(vertex_matrix=mesh.vertices, face_matrix=mesh.faces))
    detector.compute_selection_by_self_intersections_per_face()
    alarm = int(np.count_nonzero(detector.current_mesh().face_selection_array()))
    return {'vertices': len(mesh.vertices), 'faces': len(mesh.faces),
            'finite_vertices': bool(np.isfinite(mesh.vertices).all()),
            'physical_degenerate_faces': int(np.count_nonzero(~valid)),
            'watertight': bool(mesh.is_watertight), 'winding_consistent': bool(mesh.is_winding_consistent),
            'components': len(trimesh.graph.connected_components(mesh.face_adjacency, nodes=np.arange(len(mesh.faces)))),
            'self_intersection_alarm_faces': alarm, 'exact_embedding_certificate': False,
            'angles': {str(t): {'valid_small_face_fraction_of_all': float(np.count_nonzero(valid & (angles < t)) / len(areas)),
                               'valid_small_area_fraction': float(areas[valid & (angles < t)].sum() / areas[valid].sum())}
                       for t in (10, 5, 1)}}


def analytic_residual(poly, body, knots, radius):
    points = np.asarray(poly.points, dtype=np.float64)
    field = initial_field(points, body)
    for start, end in zip(knots[:-1], knots[1:]):
        field = np.maximum(field, -capsule_field(points, start, end, radius))
    return {'abs_field_p50_p95_p99_max': np.percentile(np.abs(field), [50, 95, 99, 100]).tolist(),
            'scope': '连续解析集合场的顶点残差；该场非精确SDF，不解释为距离上界'}


def vertex_distance(source, target):
    # VTK批量点到三角面最近距离只覆盖所有源顶点，不证明面内最大距离。
    sampled = source.compute_implicit_distance(target)
    values = np.abs(sampled.point_data['implicit_distance'])
    return {'p50_p95_p99_max_mm': np.percentile(values, [50, 95, 99, 100]).tolist(),
            'scope': '全部顶点到对方三角面的浮点距离，非连续距离证书'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sources', type=Path, nargs=2, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    frozen = args.output / '运行前冻结源码'
    frozen.mkdir()
    methods = []
    for name in ('conditioned_extraction.py', 'run_extraction_ablation.py', 'material_state.py', 'timed_paths.py'):
        shutil.copyfile(Path(__file__).parent / name, frozen / name)
        methods.append({'file': name, 'sha256': digest(frozen / name)})
    inputs = []
    for batch in args.sources:
        asset = json.loads((batch / '时间轨迹/01-时间轨迹资产清单.json').read_text(encoding='utf-8'))
        knots = np.load(batch / '时间轨迹' / asset['assets'][0]['file'])['knots_mm']
        for body in asset['bodies']:
            path = batch / f'{body}_10Hz/02-最终材料场.npz'
            data = np.load(path)
            inputs.append((body, data['field'], data['axis_mm'], knots, path, digest(path)))
    manifest = {'created_at_beijing': beijing_now(), 'scope': '已见开发输入，同源四方法消融',
                'methods': methods, 'inputs': [{'file': str(x[4]), 'sha256': x[5]} for x in inputs]}
    (args.output / '01-运行前方法与输入冻结.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    rows = []
    for index, (body, field, axis, knots, path, expected) in enumerate(inputs):
        if digest(path) != expected:
            raise ValueError('运行前材料场发生变化')
        baseline = None
        for structured, zero in ((False, False), (True, False), (False, True), (True, True)):
            poly, info = extract(field, axis, structured, zero)
            stem = f'{index}_{body}_structured{int(structured)}_zero{int(zero)}'
            saved = args.output / f'{stem}.vtp'
            poly.save(saved)
            actual = pv.read(saved)
            if baseline is None:
                baseline = actual
            row = {'input_index': index, 'body': body, 'source_sha256': expected,
                   'spacing_mm': float(axis[1] - axis[0]), 'method': info,
                   'file': saved.name, 'sha256': digest(saved), 'metrics': metrics(actual),
                   'analytic_vertex_residual': analytic_residual(actual, body, knots, 0.4),
                   'candidate_vertices_to_baseline': vertex_distance(actual, baseline),
                   'baseline_vertices_to_candidate': vertex_distance(baseline, actual)}
            rows.append(row)
            record = {'updated_at_beijing': beijing_now(), 'status': 'running', 'planned': 32,
                      'freeze_sha256': digest(args.output / '01-运行前方法与输入冻结.json'), 'rows': rows}
            (args.output / '02-同源提取四方法结果.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
            print(json.dumps({'input': index, 'structured': structured, 'zero': zero,
                              'degenerate': row['metrics']['physical_degenerate_faces'],
                              'intersection_alarm': row['metrics']['self_intersection_alarm_faces']}, ensure_ascii=False), flush=True)
    # 方法、输入及保存对象重新核对后才登记完整终态，原材料场始终不写回。
    if any(digest(frozen / row['file']) != row['sha256'] for row in methods):
        raise ValueError('冻结源码副本改变')
    if any(digest(item[4]) != item[5] for item in inputs):
        raise ValueError('原材料场改变')
    if any(digest(args.output / row['file']) != row['sha256'] for row in rows):
        raise ValueError('保存网格改变')
    record.update(status='complete', updated_at_beijing=beijing_now())
    (args.output / '02-同源提取四方法结果.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
