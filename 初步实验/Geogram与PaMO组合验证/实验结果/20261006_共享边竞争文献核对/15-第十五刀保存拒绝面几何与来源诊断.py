"""只读定位真实拒绝面和三条相邻边，不调参、不重新生成未完成刀。"""
from pathlib import Path
from fractions import Fraction
import json
import numpy as np
import trimesh
from run_constrained_batch import RemoteQuality
from run_geometry_study import now, save
from audit_followup_candidate import sha256, quality_distribution, _triangle_quality_values

here = Path(__file__).parent
study = Path('D:/GraduationProject_切削排斥证据/20261006_Geogram共享边竞争生成真实CT连续验证')
mp = study/'43-共享边竞争生成真实CT十六刀冻结清单.json'
manifest = json.loads(mp.read_text('utf8'))
for path, expected in manifest['modules'].items():
    assert sha256(Path(path)) == expected
rp = study/'真实CT完整父反馈结果/01-真实CT十六刀完整父反馈记录.json'
record = json.loads(rp.read_text('utf8'))
assert record['status'] == 'completed_with_recorded_outcomes' and len(record['routes'][0]['events']) == 16
event = record['routes'][0]['events'][14]
assert event['status'] == 'quality_generation_rejected' and event['generation_returncode'] == 0
assert event['geogram_execution']['returncode'] == 0
folder = Path(event['parent_path']).parents[2]/'event_14'
generation = folder/'generation'
trace_path = generation/'01-冻结机制执行记录.json'
trace = json.loads(trace_path.read_text('utf8'))
assert trace['status'] == 'initial_quality_candidate_not_accepted'
source = generation/'initial.obj'
mesh = trimesh.load(source, process=False)
assert quality_distribution(mesh) == trace['initial_quality']
label_path = generation/'initial_labels.json'
labels = np.asarray(json.loads(label_path.read_text('utf8'))['operand_bits'])
q, angles, areas = _triangle_quality_values(mesh.vertices, mesh.faces)
invalid = ~(np.isfinite(q) & np.isfinite(angles) & np.isfinite(areas) & (areas > 1e-12))
assert int(invalid.sum()) == trace['initial_quality']['invalid_faces'] == 1
incident = {}
for face_id, face in enumerate(mesh.faces):
    for a, b in zip(face, np.roll(face, -1)):
        incident.setdefault(tuple(sorted(map(int, (a, b)))), []).append(face_id)
parent, tool = [trimesh.load(Path(event[key]), process=False) for key in ('parent_path', 'tool_path')]
inherited = set(tuple(sorted(tuple(p) for p in tri)) for tri in np.concatenate((parent.triangles, tool.triangles)))
rows = []
for face_id in np.flatnonzero(invalid):
    face = mesh.faces[face_id]
    triangle = mesh.vertices[face]
    exact = [[Fraction(float(x)) for x in point] for point in triangle]
    u, v = [[point[k]-exact[0][k] for k in range(3)] for point in exact[1:]]
    cross = [u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0]]
    edges = []
    for edge_id in range(3):
        a, b, c = map(int, np.roll(face, -edge_id))
        owners = incident[tuple(sorted((a, b)))]
        assert len(owners) == 2
        neighbor = next(owner for owner in owners if owner != face_id)
        d = next(int(vertex) for vertex in mesh.faces[neighbor] if vertex not in (a, b))
        normal = mesh.face_normals[neighbor]
        replacement = np.asarray([[c, d, b], [d, c, a]])
        new_triangles = mesh.vertices[replacement]
        new_cross = np.cross(new_triangles[:, 1]-new_triangles[:, 0], new_triangles[:, 2]-new_triangles[:, 0])
        edges.append({'edge': [a, b], 'length_mm': float(np.linalg.norm(mesh.vertices[a]-mesh.vertices[b])),
            'neighbor_face_id': int(neighbor), 'neighbor_area_mm2': float(areas[neighbor]),
            'neighbor_operand_bits': int(labels[neighbor]), 'mixed_source': bool(labels[face_id] != labels[neighbor]),
            'neighbor_unstable_under_frozen_area_rule': bool(areas[neighbor] <= 1e-12),
            'new_diagonal_already_exists_or_repeats_vertex': c == d or tuple(sorted((c, d))) in incident,
            'stable_plane_deviation_mm': float(np.max(np.abs((mesh.vertices[[a, b, c, d]]-mesh.vertices[a])@normal))),
            'replacement_signed_double_area_mm2': (new_cross@normal).tolist(),
            'replacement_positive_area_under_frozen_rule': bool(np.all(new_cross@normal > 2e-12))})
    rows.append({'face_id': int(face_id), 'operand_bits': int(labels[face_id]),
        'vertices_mm': triangle.tolist(), 'area_mm2': float(areas[face_id]), 'minimum_angle_deg': float(angles[face_id]),
        'finite_coordinates': bool(np.isfinite(triangle).all()), 'exact_cross_product_zero': all(x == 0 for x in cross),
        'exact_cross_product_fraction': [[str(x.numerator), str(x.denominator)] for x in cross],
        'unchanged_parent_or_tool_triangle': tuple(sorted(tuple(p) for p in triangle)) in inherited,
        'edges': edges})
stages = []
for name in ('exact_cleaned_source', 'source_repaired', 'initial_before_repair', 'initial'):
    path = generation/(name+'.obj')
    stages.append({'stage': name, 'path': str(path), 'sha256': sha256(path),
        'quality': quality_distribution(trimesh.load(path, process=False))})
output = here/'16-第十五刀保存拒绝面几何来源诊断.json'
assert not output.exists()
save(output, {'生成时间': now(), '修改时间及修改内容': '首次重读第十五刀拒绝面及三条相邻边',
    '文档概述': '区分面积门控拒绝、准确零面积及跨来源限制；几何生成和原拒绝状态未改',
    '索引目录': ['stages', 'rows'], 'status': 'completed_saved_refusal_face_geometry_and_source_diagnosis',
    'source_record_sha256': sha256(rp), 'generation_trace_sha256': sha256(trace_path), 'code_sha256': sha256(Path(__file__)),
    'initial_obj_sha256': sha256(source), 'initial_labels_sha256': sha256(label_path),
    'local_competing_strategy_executed_on_rejected_event': 'adaptive_local_quality' in event,
    'GPU_calls': 0, 'new_generation_calls': 0, 'stages': stages, 'rows': rows})
print('第十五刀拒绝面只读诊断完成', len(rows), '面；原父链和拒绝状态未改', flush=True)
