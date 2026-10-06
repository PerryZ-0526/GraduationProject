"""复算第八轮141份保存输出，保留人为终止和原142次尝试分母。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import ast
import hashlib
import json
import numpy as np
import trimesh
import pyvista as pv
import vtk

here = Path(__file__).resolve().parent
folder = here / '第八轮原生全部重复与诊断输出'
record_path = folder / '01-原生十一同输入交错质量速度记录.json'
record = json.loads(record_path.read_text('utf8'))
assert record['status'] == 'failed_actual_native_paired_development'
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
scope = {'np': np, 'trimesh': trimesh, 'pv': pv, 'vtk': vtk}
# 只提取纯复算函数，避免执行旧入口的写盘和远程调用。
for filename, names in [('04-原版生成阶段同输入基线.py', ['quality']),
                        ('122-有界邻域生成全部重复质量几何速度复算.py', ['timing', 'distances'])]:
    module = ast.parse((here / filename).read_text('utf8'))
    functions = [n for n in module.body if isinstance(n, ast.FunctionDef) and n.name in names]
    assert len(functions) == len(names)
    exec(compile(ast.Module(body=functions, type_ignores=[]), filename, 'exec'), scope)
output = here / '167-超长版本全部保存质量几何与失败复算.json'
assert not output.exists()
summary = {'生成时间': datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),
           '修改时间及修改内容': '首次独立复算全部保存对象和已完成十案例配对',
           '文档概述': 'CT末刀调用人为终止，无输出；不恢复为完整成功评价',
           '索引目录': ['cases', 'all_saved_quality', 'failures'], 'status': 'running',
           'source_record_sha256': sha(record_path), 'planned_attempts': 154,
           'actual_attempts': len(record['rows']), 'all_saved_quality': [], 'cases': [],
           'failures': [r for r in record['rows'] if r['returncode'] != 0],
           'intervention_record_sha256': sha(here / '141-已确认超长候选调用终止记录.json')}

def save():
    """逐步保留实际完成证据，最后才能写完整复算终态。"""
    output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', 'utf8')

save()
qualities = {}
for run in record['rows']:
    if run['returncode'] != 0: continue
    path = folder / f"{run['case_index']:02d}" / Path(run['mesh_path']).name
    assert sha(path) == run['mesh_sha256']
    quality = scope['quality'](path)
    assert quality['faces'] == run['native_timing']['faces']
    key = (run['case_index'], run['method'], run['repeat'])
    qualities[key] = quality
    summary['all_saved_quality'].append({'case_index': key[0], 'method': key[1], 'repeat': key[2],
                                         'mesh_sha256': sha(path), 'quality': quality})
save()
for i in range(11):
    case = {'index': i, 'methods': {}}
    first = {}
    for method in ['baseline', 'candidate']:
        runs = [r for r in record['rows'] if r['case_index'] == i and r['method'] == method and r['returncode'] == 0]
        repeats = [r for r in runs if r['repeat'] >= 0]
        entry = {'saved_count': len(runs), 'measured_repeats': len(repeats)}
        if repeats:
            entry['boolean_timing'] = scope['timing']([r['native_timing']['boolean_ms'] for r in repeats])
            entry['bad_face_range'] = [min(qualities[(i, method, r['repeat'])]['below_10_faces'] for r in repeats),
                                       max(qualities[(i, method, r['repeat'])]['below_10_faces'] for r in repeats)]
        if (i, method, 0) in qualities:
            first[method] = folder / f'{i:02d}' / f'{method}_r00.obj'
            entry['first_quality'] = qualities[(i, method, 0)]
            audited = next(a for a in record['native_audits'] if a['case_index'] == i and a['method'] == method)
            path = folder / f'{i:02d}' / Path(audited['audit_path']).name
            assert sha(path) == audited['audit_sha256'] and sha(first[method]) == audited['mesh_sha256']
            audit = json.loads(path.read_text('utf8'))
            entry['first_native_audit'] = audit
            entry['first_embedded_closed'] = bool(audit['returncode'] == 0 and json.loads(audit['stdout'])['embedded_closed'])
        case['methods'][method] = entry
    if len(first) == 2:
        case['geometry'] = {'baseline_to_candidate': scope['distances'](first['baseline'], first['candidate'], 2026100600+i),
                            'candidate_to_baseline': scope['distances'](first['candidate'], first['baseline'], 2026100700+i)}
    summary['cases'].append(case)
    save()
    print(i, {m: e.get('first_quality', {}).get('below_10_faces') for m, e in case['methods'].items()}, flush=True)
assert len(summary['all_saved_quality']) == 141 and len(record['rows']) == 142 and len(summary['failures']) == 1
summary.update(status='completed_141_saved_recomputations_failed_batch_preserved',
               finished_beijing=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'))
save()
