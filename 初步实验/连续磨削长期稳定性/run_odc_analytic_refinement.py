"""固定失败源的作者提取分辨率对照，材料查询与作者其余参数保持。"""
import argparse
import json
from pathlib import Path
import sys
import numpy as np
import pyvista as pv
from timed_paths import beijing_now, digest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--dependencies', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(args.input / '评价启动前冻结方法'))
    sys.path.insert(0, str(args.dependencies))
    import torch
    from occupancy_dual_contouring import occupancy_dual_contouring
    from material_state import initial_field, capsule_field
    from run_extraction_ablation import metrics
    from pose_material import PoseMaterial, feature_review
    torch.set_num_threads(1)
    folder = args.input / '路线00'
    plan = json.loads((folder / '01-实际执行输入与方法绑定.json').read_text(encoding='utf-8'))
    asset = np.load(plan['asset'])
    record = json.loads((folder / '03-实际四方法完整记录.json').read_text(encoding='utf-8'))
    attempt = next(x for x in record['attempts'] if x['method'] == 'odc_analytic' and x['material_version'] == 400)
    knots = asset['knots_mm'][asset['knot_times_s'] <= asset['times_s'][400]]
    binding = {'created_at_beijing': beijing_now(), 'asset_sha256': digest(plan['asset']),
               'baseline_sha256': digest(attempt['file']), 'source_sha256': digest(__file__),
               'author_sha256': digest(args.input / '评价启动前冻结方法/occupancy_dual_contouring.py'),
               'route': 0, 'event': 400, 'grids': [120, 240], 'other_parameters': '作者默认，批量1000000，范围±3.6毫米',
               'scope': '已见失败源单因素诊断；不回写独立评价或宣称所有输入已修复'}
    (args.output / '01-细化前固定输入与参数.json').write_text(json.dumps(binding, ensure_ascii=False, indent=2), encoding='utf-8')
    state = PoseMaterial(plan['body'], asset['rotation'], asset['shift_mm'])
    extractor = occupancy_dual_contouring('cpu')
    rows = []
    for grid in binding['grids']:
        counts = {'calls': 0, 'points': 0}

        def query(points):
            array = points.detach().cpu().numpy()
            value = initial_field((array - state.shift) @ state.rotation, state.body)
            for a, b in zip(knots[:-1], knots[1:]):
                value = np.maximum(value, -capsule_field(array, a, b, .4))
            counts['calls'] += 1
            counts['points'] += len(array)
            return torch.from_numpy(np.asarray(np.clip(value, -.12, .12), dtype=np.float64))

        vertices, faces = extractor.extract_mesh(query, min_coord=[-3.6] * 3, max_coord=[3.6] * 3, num_grid=grid, batch_size=1000000)
        vertices, faces = vertices.numpy(), faces.numpy().reshape(-1, 3)
        file = args.output / f'作者解析源网格_{grid}.vtp'
        pv.PolyData(vertices, np.column_stack((np.full(len(faces), 3), faces)).ravel()).save(file)
        actual = pv.read(file)
        baseline_equal = None
        if grid == 120:
            old = pv.read(attempt['file'])
            baseline_equal = bool(np.array_equal(actual.points, old.points) and np.array_equal(actual.faces, old.faces))
            if not baseline_equal:
                raise ValueError('原分辨率不复现，禁止把细化结果当作单因素对照')
        rows.append({'grid': grid, 'extraction_spacing_mm': 7.2 / grid, 'file': str(file), 'sha256': digest(file),
                     'metrics': metrics(actual), 'feature_probes': feature_review(actual, state, knots),
                     'query_counts': counts, 'original_output_bitwise_equal': baseline_equal})
        print(json.dumps({'grid': grid, 'components': rows[-1]['metrics']['components']}, ensure_ascii=False), flush=True)
    (args.output / '02-两分辨率实际终态.json').write_text(json.dumps({'updated_at_beijing': beijing_now(), 'rows': rows}, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
