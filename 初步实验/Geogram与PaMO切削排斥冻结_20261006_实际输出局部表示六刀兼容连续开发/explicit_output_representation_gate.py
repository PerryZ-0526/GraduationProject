"""输出门控显式绑定物理保存对象与实际GPU局部表示，保留旧世界FP32诊断。"""
from pathlib import Path
import hashlib
import json
import numpy as np
import trimesh
from exact_embedding_gate import mesh_valid_full_embedding_legacy as mesh_valid_full_embedding, stored_mesh_sha256


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit_output_representation(mesh, certificate, folder, origin_name):
    """实际读回对象须绑定执行源，并同时通过CUDA、Warp面积及完整嵌入检查。"""
    folder = Path(folder)
    probe_path = folder / '01-同源实际CUDA与Warp编码复核.json'
    execution_path = folder / '02-实际表示绑定与GPU执行.json'
    probe = json.loads(probe_path.read_text('utf8'))
    execution = json.loads(execution_path.read_text('utf8'))
    legacy_valid, metrics = mesh_valid_full_embedding(mesh, certificate)
    physical_hash = stored_mesh_sha256(mesh)
    physical_bound = certificate.get('saved_mesh_sha256', certificate.get('saved_sha256')) == physical_hash
    physical_ok = bool(physical_bound and certificate.get('embedded_closed') and
                       metrics['finite'] and metrics['zero_area_faces'] == 0 and
                       metrics['watertight'] and metrics['winding_consistent'] and
                       metrics['vertex_manifold_closed'])
    source_bound = bool(execution.get('bindings') and execution['bindings'][0]['sha256'] == physical_hash)
    execution_ok = bool(execution['execution']['returncode'] == 0 and probe['status'] == 'completed')
    selected = [r for r in probe['rows'] if r['origin_name'] == origin_name]
    kinds_ok = len(selected) == 2 and {r['kind'] for r in selected} == {'CUDA', 'Warp'}
    results = []
    cuda_values = None
    for row in sorted(selected, key=lambda r: r['kind']):
        path = folder / (origin_name + '_' + row['kind'] + '.obj')
        encoded = trimesh.load(path, process=False)
        values = np.asarray(encoded.vertices)
        scale = float(row['scale'])
        origin = np.asarray(row['origin_mm'], dtype=np.float64)
        # 不仅检查摘要，还核对保存面及编码公式，防止同面数的其他对象冒充。
        if row['kind'] == 'CUDA':
            expected = (np.asarray(mesh.vertices) - origin).astype(np.float32).astype(np.float64)
            cuda_values = expected
            formula_ok = scale == 1.0 and np.array_equal(values, expected)
        else:
            expected = None if cuda_values is None else (cuda_values * scale).astype(np.float32).astype(np.float64)
            formula_ok = scale > 0 and expected is not None and np.array_equal(values, expected)
        faces_ok = np.array_equal(encoded.faces, mesh.faces)
        t = values[encoded.faces] / scale if scale > 0 else np.full((1, 3, 3), np.nan)
        area = .5 * np.linalg.norm(np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0]), axis=1)
        native = row['embedding']
        passed = bool(sha256(path) == row['encoded_sha256'] and formula_ok and faces_ok and
                      np.isfinite(values).all() and np.isfinite(area).all() and np.all(area > 1e-12) and
                      native.get('embedded_closed') and native.get('self_intersection_pairs') == 0 and
                      native.get('vertices') == len(mesh.vertices) and native.get('faces') == len(mesh.faces))
        results.append({'kind': row['kind'], 'passed': passed, 'formula_bound': bool(formula_ok),
                        'faces_unchanged': bool(faces_ok), 'encoded_sha256': sha256(path),
                        'minimum_physical_area_mm2': float(area.min()), 'embedding': native})
    # 两种实际表示须使用同一声明原点，不按世界转换或单独的面积检查放行。
    origin_ok = kinds_ok and np.array_equal(selected[0]['origin_mm'], selected[1]['origin_mm'])
    accepted = bool(physical_ok and source_bound and execution_ok and kinds_ok and origin_ok and
                    all(r['passed'] for r in results))
    return accepted, {'accepted': accepted, 'legacy_world_FP32_gate_accepted': legacy_valid,
                      'legacy_metrics': metrics, 'physical_certificate_bound': physical_bound,
                      'execution_source_bound': source_bound, 'actual_representation_checks': results,
                      'probe_sha256': sha256(probe_path), 'execution_sha256': sha256(execution_path),
                      'continuous_geometry_certified': False}
