"""作者ODC与VTK同材料对照，区分格点插值查询和解析累计材料查询。"""
import argparse
import faulthandler
import json
from pathlib import Path
import shutil
import sys
import time
import numpy as np
import pyvista as pv
from scipy.interpolate import RegularGridInterpolator
from timed_paths import beijing_now, digest


def main():
    faulthandler.enable()
    parser = argparse.ArgumentParser()
    parser.add_argument('--dependencies', type=Path, required=True)
    parser.add_argument('--author', type=Path, required=True)
    parser.add_argument('--material', type=Path, required=True)
    parser.add_argument('--trajectory', type=Path, required=True)
    parser.add_argument('--body', choices=('thin_wall', 'gap'), required=True)
    parser.add_argument('--query', choices=('grid', 'analytic'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    frozen = args.output / '运行前冻结源码'
    frozen.mkdir()
    methods = []
    for name in ('run_odc_comparison.py', 'material_state.py', 'conditioned_extraction.py',
                 'audit_feature_probes.py', 'run_extraction_ablation.py', 'timed_paths.py'):
        shutil.copyfile(Path(__file__).parent / name, frozen / name)
        methods.append({'file': name, 'sha256': digest(frozen / name)})
    shutil.copyfile(args.author / 'occupancy_dual_contouring.py', frozen / 'occupancy_dual_contouring.py')
    shutil.copyfile(args.author / 'LICENSE', frozen / '作者许可证.txt')
    author_sha = digest(frozen / 'occupancy_dual_contouring.py')
    author_identity = json.loads((args.author / '01-作者代码与许可证来源.json').read_text(encoding='utf-8'))
    if author_sha != next(x['sha256'] for x in author_identity['files'] if x['file'] == 'occupancy_dual_contouring.py'):
        raise ValueError('作者源码摘要与下载身份不一致')
    runtime = json.loads((args.author / '02-实际CPU依赖版本.json').read_text(encoding='utf-8'))
    plan = {'created_at_beijing': beijing_now(), 'body': args.body, 'query': args.query,
            'material': str(args.material), 'material_sha256': digest(args.material),
            'trajectory': str(args.trajectory), 'trajectory_sha256': digest(args.trajectory),
            'methods': methods, 'author_sha256': author_sha, 'author_identity': author_identity,
            'runtime': runtime, 'scope': '作者原代码CPU终帧开发对照；不是GPU性能或千步表面交付证据'}
    (args.output / '01-运行前方法输入与作者版本.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding='utf-8')
    sys.path.insert(0, str(frozen))
    sys.path.insert(0, str(args.dependencies))
    import torch
    from occupancy_dual_contouring import occupancy_dual_contouring
    from material_state import initial_field, capsule_field
    from conditioned_extraction import extract
    from run_extraction_ablation import metrics, analytic_residual
    from audit_feature_probes import crossings, tool_clearance
    if torch.__version__ != runtime['torch_version'] or torch.cuda.is_available():
        raise ValueError('本批固定CPU依赖与运行条件不一致')
    torch.set_num_threads(1)
    material = np.load(args.material)
    field, axis = material['field'], material['axis_mm']
    spacing = float(axis[1] - axis[0])
    knots = np.load(args.trajectory)['knots_mm']
    interpolator = RegularGridInterpolator((axis, axis, axis), field, bounds_error=True)

    def analytic(points):
        value = initial_field(points, args.body)
        for a, b in zip(knots[:-1], knots[1:]):
            value = np.maximum(value, -capsule_field(points, a, b, .4))
        return np.clip(value, -2 * spacing, 2 * spacing)

    query_counts = {'calls': 0, 'points': 0}

    def implicit(points):
        # CPU回调使用原NumPy集合函数；作者只使用其符号，不假设这些值是精确SDF。
        array = points.detach().cpu().numpy()
        value = interpolator(array) if args.query == 'grid' else analytic(array)
        query_counts['calls'] += 1
        query_counts['points'] += len(array)
        return torch.from_numpy(np.asarray(value, dtype=np.float64))

    # 单列两种信息源在格点上的符号差，不忽略零附近分类，也不混为同一输入权限。
    points = np.stack(np.meshgrid(axis, axis, axis, indexing='ij'), axis=-1).reshape(-1, 3)
    rebuilt = analytic(points).reshape(field.shape)
    source_comparison = {'grid_vs_analytic_field_max': float(np.max(np.abs(rebuilt - field))),
                         'grid_vs_analytic_negative_classification_changes': int(np.count_nonzero((rebuilt < 0) != (field < 0))),
                         'scope': '同解析几何不同浮点执行路径；接近零的分类差仍完整记录'}
    del points, rebuilt
    rows = []
    for label, zero in (('vtk_raw', False), ('vtk_zero', True), ('author_odc', None)):
        started = time.perf_counter()
        if label == 'author_odc':
            extractor = occupancy_dual_contouring('cpu')
            vertices, faces = extractor.extract_mesh(implicit, min_coord=[float(axis[0])] * 3,
                                                     max_coord=[float(axis[-1])] * 3, num_grid=len(axis) - 1,
                                                     batch_size=1000000)
            vertices, faces = vertices.cpu().numpy(), faces.cpu().numpy().reshape(-1, 3)
            poly = pv.PolyData(vertices, np.column_stack((np.full(len(faces), 3), faces)).ravel())
            info = {'author_code_unchanged': True, 'query': args.query, 'torch_default_dtype': str(torch.get_default_dtype()),
                    'num_grid': len(axis) - 1, 'batch_size': 1000000, 'other_extract_parameters': '作者默认参数',
                    'actual_coordinate_dtype': str(vertices.dtype), 'query_counts': dict(query_counts)}
        else:
            poly, info = extract(field, axis, True, zero)
        elapsed = time.perf_counter() - started
        file = args.output / f'02-{label}.vtp'
        poly.save(file)
        actual = pv.read(file)
        review = metrics(actual)
        probes = []
        if args.body == 'thin_wall':
            direction, expected = 2, [-.18, .18]
            positions = [(x, y) for x in (-1.95, 1.95) for y in (-1.65, 1.65)]
        else:
            direction, expected = 0, [-1.92, -.12, .12, 1.92]
            positions = ([(y, z) for y in (-1.75, 1.75) for z in (-.75, .75)]
                         + [(y, z) for y in (-1.5, 1.5) for z in (0, .3)])
        for fixed in positions:
            clearance = tool_clearance(direction, fixed, knots)
            if clearance <= 0:
                raise ValueError('初态尺寸探针不满足未切削前提')
            values = crossings(actual, direction, fixed)
            observed = values['crossings_mm']
            error = None if len(observed) != len(expected) else float(np.max(np.abs(np.asarray(observed) - expected)))
            probes.append(dict(values, fixed_coordinates_mm=fixed, crossing_error_max_mm=error,
                               tool_clearance_lower_bound_mm=clearance))
        rows.append({'method': label, 'identity': info, 'file': str(file), 'sha256': digest(file),
                     'metrics': review, 'feature_probes': probes, 'analytic_vertex_residual': analytic_residual(actual, args.body, knots, .4),
                     'cpu_extraction_seconds_observation': elapsed})
        record = {'updated_at_beijing': beijing_now(), 'status': 'running', 'planned_methods': 3,
                  'source_comparison': source_comparison, 'rows': rows}
        (args.output / '03-同材料提取比较记录.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({'method': label, 'degenerated': review['physical_degenerate_faces'],
                          'alarm': review['self_intersection_alarm_faces']}, ensure_ascii=False), flush=True)
    # 终态继续绑定实际材料、轨迹和作者原字节，不把来源权限差异隐去。
    if digest(args.material) != plan['material_sha256'] or digest(args.trajectory) != plan['trajectory_sha256']:
        raise ValueError('原材料或轨迹摘要变化')
    if digest(frozen / 'occupancy_dual_contouring.py') != author_sha or any(digest(frozen / item['file']) != item['sha256'] for item in methods):
        raise ValueError('运行前冻结源码变化')
    record.update(status='complete', updated_at_beijing=beijing_now())
    (args.output / '03-同材料提取比较记录.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
