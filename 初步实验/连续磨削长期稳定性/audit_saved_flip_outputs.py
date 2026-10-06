"""终态重读160保存对象，重新核算翻边证书并实查三种新几何。"""
import argparse
import json
from pathlib import Path
import sys
import numpy as np
import pyvista as pv


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--project', type=Path, required=True)
    parser.add_argument('--input', type=Path, required=True)
    args = parser.parse_args()
    output = args.input / '05-终态保存对象与连续面片证书复审.json'
    if output.exists():
        raise ValueError('复审文件禁止覆盖')
    sys.path.insert(0, str(args.project / '初步实验/连续磨削长期稳定性'))
    from timed_paths import beijing_now, digest
    from audit_pose_full_embedding import checker, obj_bytes
    sys.path.insert(0, str(args.input / '运行前实际源码'))
    from run_vtk_sliver_flip_audit import certify_flips
    plan = json.loads((args.input / '01-完整回归运行前方法与参数.json').read_text(encoding='utf-8'))
    status = json.loads((args.input / '04-实际批次状态.json').read_text(encoding='utf-8'))
    ledger = args.input / '03-完整160对象修复记录.jsonl'
    rows = [json.loads(x) for x in ledger.read_text(encoding='utf-8').splitlines()]
    if status['status'] != 'complete' or len(rows) != 160 or digest(ledger) != status['ledger_sha256']:
        raise ValueError('原160分母或终态绑定不成立')
    executable = Path('D:/GraduationProject实验依赖/CGAL_20261006/构建/Release/exact_mesh_audit.exe')
    if digest(executable) != plan['executable_sha256']:
        raise ValueError('当前检查器摘要不匹配')
    reviews, cache = [], {}
    for row in rows:
        source, file = Path(row['source_file']), Path(row['file'])
        first, second = pv.read(source), pv.read(file)
        faces = first.faces.reshape(-1, 4)[:, 1:]
        new_faces = second.faces.reshape(-1, 4)[:, 1:]
        geometry = certify_flips(first.points, faces, new_faces, row['repair']['flips'])
        same_vertices = np.array_equal(first.points.view(np.uint64), second.points.view(np.uint64))
        same_material = np.array_equal(first.point_data['material'], second.point_data['material'])
        changed_indices = np.flatnonzero(np.any(new_faces != faces, axis=1)).tolist()
        matched = digest(source) == row['source_sha256'] and digest(file) == row['sha256']
        matched &= geometry == row['geometry'] and same_vertices and same_material and changed_indices == row['changed_face_indices']
        result = None
        if row['repair']['flips']:
            import hashlib
            text = obj_bytes(second.points, new_faces)
            sha = hashlib.sha256(text).hexdigest()
            if sha not in cache:
                obj = args.input / f'复审_{sha}.obj'
                obj.write_bytes(text)
                cache[sha] = checker(executable, obj)
            result = cache[sha]
            matched &= result['returncode'] == 0 and result['certificate'] == row['exact_result']['certificate']
        else:
            matched &= source.read_bytes() == file.read_bytes()
        reviews.append({'route': row['route'], 'method': row['method'], 'event': row['event'],
                        'matched': bool(matched), 'vertices_bitwise_same': bool(same_vertices),
                        'material_scalar_same': bool(same_material), 'changed_face_count': len(changed_indices),
                        'geometry': geometry, 'fresh_exact_result': result})
    result = {'reviewed_at_beijing': beijing_now(), 'reviewer_sha256': digest(__file__), 'rows': reviews,
              'matched_objects': sum(x['matched'] for x in reviews), 'fresh_distinct_exact_executions': len(cache),
              'scope': '源到修复面片的连续上界及保存契约；非权威材料到提取网格的整体误差证书'}
    with output.open('x', encoding='utf-8') as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
    print(json.dumps({'matched': result['matched_objects'], 'planned': 160, 'fresh_exact_executions': len(cache)}))


if __name__ == '__main__':
    main()
