"""只读核查未切削薄壁与窄缝射线；不能替代全域几何证书。"""
import argparse
import json
from pathlib import Path
import shutil
import numpy as np
import pyvista as pv
from timed_paths import beijing_now, digest


def crossings(poly, direction, fixed):
    triangles = np.asarray(poly.points, dtype=np.float64)[poly.faces.reshape(-1, 4)[:, 1:]]
    others = [i for i in range(3) if i != direction]
    projected = triangles[:, :, others]
    a = projected[:, 0]
    edge1, edge2 = projected[:, 1] - a, projected[:, 2] - a
    delta = np.asarray(fixed) - a
    determinant = edge1[:, 0] * edge2[:, 1] - edge1[:, 1] * edge2[:, 0]
    # 与射线平行或退化的投影不产生孤立交点，数量明确保留。
    usable = determinant != 0
    u = np.divide(delta[:, 0] * edge2[:, 1] - delta[:, 1] * edge2[:, 0],
                  determinant, out=np.zeros(len(a)), where=usable)
    v = np.divide(edge1[:, 0] * delta[:, 1] - edge1[:, 1] * delta[:, 0],
                  determinant, out=np.zeros(len(a)), where=usable)
    hit = usable & (u >= -1e-12) & (v >= -1e-12) & (u + v <= 1 + 1e-12)
    positions = (triangles[:, 0, direction] + u * (triangles[:, 1, direction] - triangles[:, 0, direction])
                 + v * (triangles[:, 2, direction] - triangles[:, 0, direction]))[hit]
    positions.sort()
    # 仅评价器合并同一位置的多面命中；网格、索引和材料场都不修改。
    merged = []
    for value in positions:
        if not merged or value - merged[-1] > 1e-7:
            merged.append(float(value))
    return {'crossings_mm': merged, 'raw_hit_count': int(hit.sum()),
            'parallel_projected_faces': int(np.count_nonzero(~usable)),
            'merge_tolerance_mm': 1e-7}


def tool_clearance(direction, fixed, knots):
    others = [i for i in range(3) if i != direction]
    # 工具中心线投影到射线正交平面，最短距离是整条无限射线的精确解析下界。
    endpoints = knots[:, others]
    values = []
    for start, end in zip(endpoints[:-1], endpoints[1:]):
        edge = end - start
        square = float(edge @ edge)
        t = 0 if square == 0 else np.clip((np.asarray(fixed) - start) @ edge / square, 0, 1)
        values.append(float(np.linalg.norm(np.asarray(fixed) - start - t * edge) - .4))
    return min(values)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    inputs = []
    ledger = json.loads((args.input / '02-完整隔离提取消融记录.json').read_text(encoding='utf-8'))
    for row in ledger['rows']:
        request = row['request']
        if request['body'] not in ('thin_wall', 'gap'):
            continue
        mesh_path = args.input / f"案例{request['case_id']:02d}/02-提取网格.vtp"
        inputs.append({'case_id': request['case_id'], 'request': request,
                       'file': str(mesh_path), 'sha256': digest(mesh_path),
                       'original_status': row['status']})
    frozen = args.output / '运行前冻结源码'
    frozen.mkdir()
    methods = []
    for name in ('audit_feature_probes.py', 'material_state.py', 'timed_paths.py'):
        shutil.copyfile(Path(__file__).parent / name, frozen / name)
        methods.append({'file': name, 'sha256': digest(frozen / name)})
    plan = {'created_at_beijing': beijing_now(), 'inputs': inputs, 'methods': methods,
            'scope': '16张实际保存网格，含原3项失败产物；仅只读特征探针，不改原终态'}
    (args.output / '01-实际输入与方法冻结.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding='utf-8')
    rows = []
    for item in inputs:
        request = item['request']
        poly = pv.read(item['file'])
        knots = np.load(request['trajectory'])['knots_mm']
        probes = []
        if request['body'] == 'thin_wall':
            direction = 2
            positions = [(x, y) for x in (-1.95, 1.95) for y in (-1.65, 1.65)]
            expected = [-.18, .18]
        else:
            direction = 0
            # 同时保留靠近棱角的旧探针，并增加平面内部探针，不能以新位置替代旧负例。
            positions = ([(y, z) for y in (-1.75, 1.75) for z in (-.75, .75)]
                         + [(y, z) for y in (-1.5, 1.5) for z in (0, .3)])
            expected = [-1.92, -.12, .12, 1.92]
        for fixed in positions:
            clearance = tool_clearance(direction, fixed, knots)
            if clearance <= 0:
                raise ValueError('探针射线可能被工具切削，不能使用初态尺寸作参照')
            observed = crossings(poly, direction, fixed)
            values = observed['crossings_mm']
            error = None if len(values) != len(expected) else float(np.max(np.abs(np.asarray(values) - expected)))
            probes.append(dict(observed, fixed_coordinates_mm=fixed, direction=direction,
                               analytic_expected_mm=expected, tool_clearance_lower_bound_mm=clearance,
                               crossing_error_max_mm=error,
                               matches_1e_6_mm=error is not None and error <= 1e-6))
        rows.append({'case_id': item['case_id'], 'body': request['body'], 'original_status': item['original_status'],
                     'saved_mesh_sha256': item['sha256'], 'probes': probes})
    # 复审后仍绑定原保存对象，失败产物的本项成功不追记为原协议完整通过。
    if any(digest(item['file']) != item['sha256'] for item in inputs):
        raise ValueError('读取期间实际保存网格改变')
    result = {'updated_at_beijing': beijing_now(), 'status': 'complete', 'planned_meshes': len(inputs),
              'rows': rows, 'scope': '每薄壁4条、每窄缝8条未切削解析射线；保留棱角并补平面内部，只覆盖这些位置；浮点评价非连续几何证书'}
    (args.output / '02-薄壁窄缝探针完整记录.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'meshes': len(rows), 'probes': sum(len(x['probes']) for x in rows),
                      'matched': sum(p['matches_1e_6_mm'] for x in rows for p in x['probes'])}, ensure_ascii=False))


if __name__ == '__main__':
    main()
