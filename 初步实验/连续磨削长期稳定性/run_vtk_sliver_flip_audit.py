"""复用既有物理翻边，完整核查160张VTK保存输出和连续面片变化上界。"""
import argparse
from fractions import Fraction
import importlib
import json
from pathlib import Path
import shutil
import sys
import numpy as np
import pyvista as pv
import trimesh
from flip_patch_geometry_bound import patch_bound, finite_controls


def cyclic_equal(first, second):
    return any(np.array_equal(first, np.roll(second, shift)) for shift in range(3))


def certify_flips(vertices, source_faces, candidate_faces, flips):
    current = source_faces.copy()
    certificates = []
    for flip in flips:
        i, j = flip['faces']
        a, b = flip['old_edge']
        c, d = flip['new_edge']
        if not (cyclic_equal(current[i], [a, b, c]) and cyclic_equal(current[j], [b, a, d])):
            return {'certified': False, 'reason': '翻边记录未绑定当次旧面片'}
        certificate = patch_bound(vertices, [a, b], [c, d])
        if not certificate['certified']:
            return certificate
        current[[i, j]] = [[c, d, b], [d, c, a]]
        certificates.append(certificate)
    if not np.array_equal(current, candidate_faces):
        return {'certified': False, 'reason': '记录操作不能重建实际候选面数组'}
    total = sum((Fraction(x['bidirectional_bound_mm_fraction']) for x in certificates), Fraction(0))
    return {'certified': True, 'patches': certificates, 'bidirectional_bound_mm_fraction': str(total),
            'bidirectional_bound_mm': float(total), 'within_1e7_mm_budget': total <= Fraction(1, 10000000),
            'scope': '保存源网格到修复网格的连续双向上界；不是原材料到网格的误差证书'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--project', type=Path, required=True)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--baseline-audit', type=Path, required=True)
    parser.add_argument('--executable', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(args.project / '初步实验/连续磨削长期稳定性'))
    from timed_paths import beijing_now, digest
    from audit_pose_full_embedding import obj_bytes, checker, vertex_manifold_closed
    oldroot = args.project / '初步实验/Geogram与PaMO组合验证'
    sys.path.insert(0, str(oldroot))
    from physical_repair_operations import SOURCES
    frozen = args.output / '运行前实际源码'
    frozen.mkdir()
    flip_file = frozen / 'physical_retriangulate.py'
    flip_file.write_text(SOURCES['physical_retriangulate.py'], encoding='utf-8')
    local_sources = [Path(__file__), Path(__file__).with_name('flip_patch_geometry_bound.py')]
    original_sources = [oldroot / n for n in ('physical_repair_operations.py', 'locality_retriangulate.py', 'locality_sliver_collapse.py', 'preserved_controller_source.py')]
    for path in local_sources + original_sources:
        shutil.copyfile(path, frozen / path.name)
    sys.path.insert(0, str(frozen))
    operation = importlib.import_module('physical_retriangulate')
    sys.path.insert(0, str(args.input / '评价启动前冻结方法'))
    from run_extraction_ablation import metrics
    from pose_material import PoseMaterial, feature_review
    baseline_plan = json.loads((args.baseline_audit / '01-全量精确核查运行前绑定.json').read_text(encoding='utf-8'))
    if digest(args.executable) != baseline_plan['executable_sha256']:
        raise ValueError('当前检查器未绑定基线完整证据')
    baseline = {x['saved_file']: x for x in (json.loads(line) for line in (args.baseline_audit / '03-逐保存对象实际核查.jsonl').read_text(encoding='utf-8').splitlines())}
    tasks = []
    for folder in sorted(args.input.glob('路线[0-9][0-9]')):
        plan = json.loads((folder / '01-实际执行输入与方法绑定.json').read_text(encoding='utf-8'))
        record = json.loads((folder / '03-实际四方法完整记录.json').read_text(encoding='utf-8'))
        if record['status'] != 'complete':
            raise ValueError('原路线未终态')
        for attempt in record['attempts']:
            if attempt['method'].startswith('vtk'):
                tasks.append(dict(attempt, route=folder.name, body=plan['body'], asset=plan['asset']))
    if len(tasks) != 160:
        raise ValueError('VTK完整分母应为160')
    binding = {'created_at_beijing': beijing_now(), 'planned': 160, 'runner_actual_path': str(Path(__file__).resolve()),
               'source_files': [{'file': str(path), 'sha256': digest(path)} for path in local_sources + original_sources],
               'actual_generated_flip_sha256': digest(flip_file), 'executable_sha256': digest(args.executable),
               'baseline_ledger_sha256': digest(args.baseline_audit / '03-逐保存对象实际核查.jsonl'),
               'input_files': [{'file': x['file'], 'sha256': x['sha256']} for x in tasks],
               'parameters': {'area_threshold_mm2': 1e-12, 'plane_tolerance_mm': 1e-8, 'repair_surface_bound_mm': 1e-7,
                              'max_flips': '初始低面积面数量', 'vertex_moves': False, 'collapse_enabled': False},
               'source_group': '同一次材料场提取的统一组标记1，不冒称骨面/钻面CSG来源标签',
               'scope': '已见八路线离线提取修复回归；不是新独立评价、GPU维护或逐事件交付'}
    (args.output / '01-完整回归运行前方法与参数.json').write_text(json.dumps(binding, ensure_ascii=False, indent=2), encoding='utf-8')
    controls = finite_controls()
    (args.output / '02-连续面片上界有限控制.json').write_text(json.dumps(controls, ensure_ascii=False, indent=2), encoding='utf-8')
    if not controls['passed']:
        raise ValueError('连续面片上界有限控制不通过')
    rows, new_cache = [], {}
    with (args.output / '03-完整160对象修复记录.jsonl').open('x', encoding='utf-8') as log:
        for task in tasks:
            source = Path(task['file'])
            if digest(source) != task['sha256'] or baseline[str(source)]['saved_sha256'] != task['sha256']:
                raise ValueError('原输入或精确证据绑定改变')
            poly = pv.read(source)
            mesh = trimesh.Trimesh(poly.points, poly.faces.reshape(-1, 4)[:, 1:], process=False)
            candidate, _, repair = operation.repair_degenerate(mesh, np.ones(len(mesh.faces), dtype=int))
            geometry = certify_flips(mesh.vertices, mesh.faces, candidate.faces, repair['flips'])
            vertices_same = bool(np.array_equal(mesh.vertices.view(np.uint64), candidate.vertices.view(np.uint64)))
            changed = not np.array_equal(mesh.faces, candidate.faces)
            actual = poly.copy()
            if changed:
                actual.faces = np.column_stack((np.full(len(candidate.faces), 3), candidate.faces)).ravel()
                # 翻边改变邻接面，重新计算显示法线；不移动顶点或改写权威材料场。
                actual.compute_normals(point_normals=True, cell_normals=False, consistent_normals=False,
                                       auto_orient_normals=False, split_vertices=False, inplace=True)
                if not np.array_equal(actual.points.view(np.uint64), mesh.vertices.view(np.uint64)) or not np.array_equal(actual.faces.reshape(-1, 4)[:, 1:], candidate.faces):
                    raise ValueError('法线计算意外修改几何')
            output = args.output / f"{task['route']}_{task['material_version']:04d}_{task['method']}.vtp"
            if changed:
                actual.save(output)
            else:
                shutil.copyfile(source, output)
            saved = pv.read(output)
            saved_faces = saved.faces.reshape(-1, 4)[:, 1:]
            if changed:
                audit = metrics(saved)
                text = obj_bytes(saved.points, saved_faces)
                import hashlib
                sha = hashlib.sha256(text).hexdigest()
                if sha not in new_cache:
                    obj = args.output / f'候选_{sha}.obj'
                    obj.write_bytes(text)
                    new_cache[sha] = checker(args.executable, obj)
                exact = new_cache[sha]
                manifold = vertex_manifold_closed(saved_faces)
            else:
                audit = task['metrics']
                exact = baseline[str(source)]['exact_result']
                manifold = baseline[str(source)]['vertex_manifold_closed']
            certificate = exact['certificate'] or {}
            exact_bound = (exact['returncode'] == 0 and certificate.get('embedded_closed', False)
                           and certificate.get('vertices') == saved.n_points and certificate.get('faces') == saved.n_cells)
            asset = np.load(task['asset'])
            state = PoseMaterial(task['body'], asset['rotation'], asset['shift_mm'])
            knots = asset['knots_mm'][asset['knot_times_s'] <= asset['times_s'][task['material_version']]]
            probes = feature_review(saved, state, knots) if changed else task['feature_probes']
            same_probes = [x['crossings_mm'] for x in probes] == [x['crossings_mm'] for x in task['feature_probes']]
            topology_same = bool(candidate.is_watertight == mesh.is_watertight and candidate.is_winding_consistent == mesh.is_winding_consistent
                                 and candidate.euler_number == mesh.euler_number and audit['components'] == task['metrics']['components'])
            accepted = bool(geometry.get('certified') and geometry.get('within_1e7_mm_budget') and vertices_same
                            and topology_same and same_probes and manifold and exact_bound and audit['physical_degenerate_faces'] == 0
                            and audit['components'] == (2 if task['body'] == 'gap' else 1))
            changed_faces = np.flatnonzero(np.any(candidate.faces != mesh.faces, axis=1)).tolist()
            row = {'route': task['route'], 'method': task['method'], 'event': task['material_version'], 'accepted': accepted,
                   'source_file': str(source), 'source_sha256': task['sha256'], 'file': str(output), 'sha256': digest(output),
                   'repair': repair, 'geometry': geometry, 'vertices_bitwise_same': vertices_same,
                   'changed_face_indices': changed_faces, 'topology_same': topology_same, 'material_probe_crossings_same': same_probes,
                   'metrics': audit, 'exact_result': exact, 'vertex_manifold_closed': manifold,
                   'normals_recomputed': changed, 'original_material_field_modified': False}
            rows.append(row)
            log.write(json.dumps(row, ensure_ascii=False) + '\n')
            log.flush()
            if len(rows) % 20 == 0:
                print(json.dumps({'reviewed': len(rows), 'planned': 160, 'accepted': sum(x['accepted'] for x in rows)}), flush=True)
                (args.output / '04-实际批次状态.json').write_text(json.dumps({'status': 'running', 'reviewed': len(rows), 'planned': 160}), encoding='utf-8')
    if any(digest(Path(x['file'])) != x['sha256'] for x in binding['source_files']) or digest(args.executable) != binding['executable_sha256']:
        raise ValueError('实际执行方法或检查器改变')
    result = {'status': 'complete', 'updated_at_beijing': beijing_now(), 'reviewed': len(rows), 'planned': 160,
              'accepted': sum(x['accepted'] for x in rows), 'changed_outputs': sum(bool(x['repair']['flips']) for x in rows),
              'new_unique_exact_geometry_executions': len(new_cache), 'ledger_sha256': digest(args.output / '03-完整160对象修复记录.jsonl'),
              'scope': binding['scope']}
    (args.output / '04-实际批次状态.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
