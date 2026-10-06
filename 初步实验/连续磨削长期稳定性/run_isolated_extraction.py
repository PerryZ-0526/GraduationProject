"""同一冻结提取方法逐案例隔离执行，保留子进程退出与完整计划分母。"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
from timed_paths import beijing_now, digest


def worker(request_path):
    import numpy as np
    import pyvista as pv
    from run_extraction_ablation import metrics, analytic_residual, vertex_distance
    from conditioned_extraction import extract
    request = json.loads(request_path.read_text(encoding='utf-8'))
    source = Path(request['field'])
    if digest(source) != request['source_sha256']:
        raise ValueError('材料输入摘要变化')
    data = np.load(source)
    field, axis = data['field'], data['axis_mm']
    knots = np.load(request['trajectory'])['knots_mm']
    original, _ = extract(field, axis, False, False)
    poly, info = extract(field, axis, request['structured'], request['zero'])
    output = request_path.parent / '02-提取网格.vtp'
    poly.save(output)
    actual = pv.read(output)
    result = dict(request, method=info, file=output.name, sha256=digest(output),
                  metrics=metrics(actual), analytic_vertex_residual=analytic_residual(actual, request['body'], knots, .4),
                  candidate_vertices_to_baseline=vertex_distance(actual, original),
                  baseline_vertices_to_candidate=vertex_distance(original, actual))
    (request_path.parent / '03-保存网格复审.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--worker', type=Path)
    parser.add_argument('--frozen', type=Path)
    parser.add_argument('--sources', type=Path, nargs=2)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.worker:
        worker(args.worker)
        return
    args.output.mkdir(parents=True, exist_ok=False)
    frozen = args.output / '运行前冻结源码'
    frozen.mkdir()
    methods = []
    for name in ('conditioned_extraction.py', 'run_extraction_ablation.py', 'material_state.py', 'timed_paths.py'):
        shutil.copyfile(args.frozen / name, frozen / name)
        methods.append({'file': name, 'sha256': digest(frozen / name)})
    shutil.copyfile(__file__, frozen / Path(__file__).name)
    methods.append({'file': Path(__file__).name, 'sha256': digest(frozen / Path(__file__).name)})
    requests = []
    for batch in args.sources:
        manifest = json.loads((batch / '时间轨迹/01-时间轨迹资产清单.json').read_text(encoding='utf-8'))
        trajectory = batch / '时间轨迹' / manifest['assets'][0]['file']
        for body in manifest['bodies']:
            source = batch / f'{body}_10Hz/02-最终材料场.npz'
            for structured, zero in ((False, False), (True, False), (False, True), (True, True)):
                requests.append({'case_id': len(requests), 'body': body, 'field': str(source),
                                 'source_sha256': digest(source), 'trajectory': str(trajectory),
                                 'trajectory_sha256': digest(trajectory), 'structured': structured, 'zero': zero})
    freeze = {'created_at_beijing': beijing_now(), 'methods': methods, 'requests': requests,
              'scope': '同源32案例固定计划；仅执行与审计进程隔离，提取方法不改'}
    freeze_path = args.output / '01-运行前固定计划与源码.json'
    freeze_path.write_text(json.dumps(freeze, ensure_ascii=False, indent=2), encoding='utf-8')
    rows = []
    for request in requests:
        folder = args.output / f"案例{request['case_id']:02d}"
        folder.mkdir()
        request_path = folder / '01-实际输入与方法.json'
        request_path.write_text(json.dumps(request, ensure_ascii=False, indent=2), encoding='utf-8')
        with (folder / '04-执行日志.log').open('wb') as log:
            result = subprocess.run([sys.executable, str(frozen / Path(__file__).name), '--worker', str(request_path)],
                                    stdout=log, stderr=subprocess.STDOUT)
        row = {'request': request, 'returncode': result.returncode, 'status': 'worker_failed'}
        output = folder / '03-保存网格复审.json'
        if result.returncode == 0 and output.exists():
            row.update(status='executed_and_reloaded', result=json.loads(output.read_text(encoding='utf-8')),
                       saved_mesh_sha256=digest(folder / '02-提取网格.vtp'))
        rows.append(row)
        record = {'updated_at_beijing': beijing_now(), 'status': 'running', 'planned': len(requests),
                  'freeze_sha256': digest(freeze_path), 'rows': rows}
        (args.output / '02-完整隔离提取消融记录.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({'case': request['case_id'], 'returncode': result.returncode,
                          'status': row['status']}, ensure_ascii=False), flush=True)
    # 所有计划事件都有真实终态；失败计入分母，不能因父进程成功而改称方法通过。
    for item in requests:
        if digest(item['field']) != item['source_sha256'] or digest(item['trajectory']) != item['trajectory_sha256']:
            raise ValueError('运行期间原材料或轨迹改变')
    if any(digest(frozen / item['file']) != item['sha256'] for item in methods):
        raise ValueError('实际冻结方法源码改变')
    record.update(status='complete', updated_at_beijing=beijing_now())
    (args.output / '02-完整隔离提取消融记录.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
