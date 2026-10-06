"""只读追踪作者歧义分支，原作者字节和输出算法不修改。"""
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
    frozen = args.input / '评价启动前冻结方法'
    sys.path.insert(0, str(frozen))
    sys.path.insert(0, str(args.dependencies))
    import torch
    from occupancy_dual_contouring import occupancy_dual_contouring
    from pose_material import PoseMaterial, extract_pose
    torch.set_num_threads(1)
    folder = args.input / '路线00'
    plan = json.loads((folder / '01-实际执行输入与方法绑定.json').read_text(encoding='utf-8'))
    asset = np.load(plan['asset'])
    record = json.loads((folder / '03-实际四方法完整记录.json').read_text(encoding='utf-8'))
    attempt = next(x for x in record['attempts'] if x['method'] == 'odc_analytic' and x['material_version'] == 400)
    author = frozen / 'occupancy_dual_contouring.py'
    author_sha = digest(author)
    lines = author.read_text(encoding='utf-8').splitlines()
    capture_line = next(i + 1 for i, text in enumerate(lines) if 'amb_chks = th.zeros' in text)
    captured = {}

    def trace(frame, event, arg):
        if event == 'line' and Path(frame.f_code.co_filename) == author and frame.f_lineno == capture_line:
            local = frame.f_locals
            captured.update(occs=local['occs'].cpu().numpy().copy(), vals_after=local['vals'].cpu().numpy().copy(),
                            ambiguous_cells=local['amb_pidx3'].cpu().numpy().copy(), previous_values=local['tmp'].cpu().numpy().copy())
        return trace

    state = PoseMaterial(plan['body'], asset['rotation'], asset['shift_mm'])
    knots = asset['knots_mm'][asset['knot_times_s'] <= asset['times_s'][400]]
    binding = {'created_at_beijing': beijing_now(), 'author_sha256': author_sha, 'source_sha256': digest(__file__),
               'asset_sha256': digest(plan['asset']), 'baseline_sha256': digest(attempt['file']),
               'capture_line': capture_line, 'route': 0, 'event': 400, 'method': 'odc_analytic', 'parameters_changed': False}
    (args.output / '01-追踪前方法与输入绑定.json').write_text(json.dumps(binding, ensure_ascii=False, indent=2), encoding='utf-8')
    extractor = occupancy_dual_contouring('cpu')
    sys.settrace(trace)
    try:
        vertices, faces, counts = extract_pose(torch, extractor, state, knots, 'analytic')
    finally:
        sys.settrace(None)
    if not captured or digest(author) != author_sha:
        raise ValueError('未捕获作者分支或作者源码改变')
    baseline = pv.read(attempt['file'])
    equal = np.array_equal(vertices, baseline.points) and np.array_equal(faces, baseline.faces.reshape(-1, 4)[:, 1:])
    np.savez(args.output / '02-实际歧义分支状态.npz', **captured, vertices=vertices, faces=faces)
    result = dict(binding, updated_at_beijing=beijing_now(), output_bitwise_equal_to_evaluation=bool(equal),
                  ambiguous_cell_observations=len(captured['ambiguous_cells']), query_counts=counts,
                  scope='作者运行中只读状态观察；相关性不是歧义分支的因果消融')
    (args.output / '03-只读追踪终态.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
