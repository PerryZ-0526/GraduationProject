"""独立重加载完整投影诊断，并取回同次投影前对象检查两类新增锚点。"""
import argparse
import json
from pathlib import Path
import shlex
import numpy as np
import trimesh
from audit_followup_candidate import sha256
from audit_published_anchor_records import check_anchor_record
from initial_encoding_saved_contract import check_initial_encoding_record
from preserved_saved_binding import collect_certificates, mesh_valid_saved_binding
from run_constrained_batch import RemoteQuality
from run_constrained_feedback import global_geometry
from run_geometry_study import execute, retrieve, save, now


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'labels', 'tool', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--port', type=int, required=True)
    args = parser.parse_args()
    record_path = args.output/'01-初态编码锚点完整投影诊断.json'
    record = json.loads(record_path.read_text(encoding='utf-8'))
    if record['status'] != 'completed_with_recorded_outcomes':
        raise ValueError('诊断尚未终态，不能生成完整保存复审')
    if record['input_sha256'] != {name:sha256(getattr(args,name)) for name in ('source','labels','tool')}:
        raise ValueError('复审输入与实际诊断输入摘要不符')
    source = trimesh.load(args.source, process=False)
    certificates = collect_certificates(record)
    remote = RemoteQuality(args.output, args.port)
    result = dict(time_beijing=now(), record_sha256=sha256(record_path), rows=[], published=False,
        scope='同次投影前对象、保存输出、固定坐标、两类新增锚点、全量嵌入和能量调用复审；非连续误差证书')
    try:
        for row, name in zip(record['rows'], ('boolean', 'expanded'), strict=True):
            folder = args.output/name
            command = shlex.split(row['execution']['command'])
            remote_before = command[command.index('--output')+1]+'/before_projection.obj'
            digest = execute(remote.client, ['sha256sum',remote_before])['stdout'].split()[0]
            before_path = folder/'before_projection.obj'
            retrieve(remote.client, remote.sftp, remote_before, before_path)
            before = trimesh.load(before_path, process=False)
            output = folder/'candidate.obj'
            mesh = trimesh.load(output, process=False)
            valid, metrics = mesh_valid_saved_binding(mesh, certificates)
            ids = np.asarray(row['vertex_original_ids'])
            original = ids >= 0
            fixed = np.array_equal(mesh.vertices[original], source.vertices[ids[original]])
            anchors = row.get('anchor_updates')
            added = row.get('projection') == 'no_free_vertices_identity' if anchors is None else (
                json.loads((folder/'anchor_updates.json').read_text(encoding='utf-8')) == anchors
                and check_anchor_record(anchors,ids)
                and all(np.array_equal(mesh.vertices[u['added_vertices']],before.vertices[u['added_vertices']]) for u in anchors['updates']))
            details = json.loads((folder/'details.json').read_text(encoding='utf-8'))
            initial = check_initial_encoding_record(source.vertices,before.vertices,before.faces,mesh.vertices,ids,row['initial_encoding_anchors'])
            trace_path = folder/'diff_trace.json'
            trace = json.loads(trace_path.read_text(encoding='utf-8'))['rows']
            numerical = (sha256(trace_path) == row['diff_trace_sha256'] and len(trace) == 50
                and all(t['finite_positions'] and t['full_energy_finite'] and np.isfinite(t['full_energy']) for t in trace)
                and row['numerical_diagnostic']['passed'])
            geometry = global_geometry(mesh, source)
            passed = bool(row['status'] == 'accepted_sampled' and valid and fixed and added and initial['passed']
                and details['initial_encoding_anchors'] == row['initial_encoding_anchors'] and numerical
                and digest == sha256(before_path) and sha256(output) == row['output_sha256']
                and np.array_equal(mesh.faces,before.faces) and mesh.euler_number == source.euler_number
                and geometry['probe_max_mm'] <= .1)
            result['rows'].append(dict(region=name, passed=passed, metrics=metrics, geometry=geometry,
                initial_encoding_contract=initial, original_fixed_exact=bool(fixed), added_anchors_exact=bool(added),
                numerical_trace_passed=bool(numerical), before_sha256=sha256(before_path), output_sha256=sha256(output)))
        result.update(outputs=len(result['rows']), passed=sum(r['passed'] for r in result['rows']))
        save(args.output/'02-完整投影诊断保存对象复审.json',result)
        print(result['passed'], '/', result['outputs'])
        if result['passed'] != result['outputs']:
            raise SystemExit(1)
    finally:
        remote.close()
