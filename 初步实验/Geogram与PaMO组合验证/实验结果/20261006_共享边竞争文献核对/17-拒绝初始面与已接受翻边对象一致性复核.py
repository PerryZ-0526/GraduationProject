"""确认低面积拒绝对象是否与已有精确检查对象相同，避免将数值门槛称为数学退化。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json
import numpy as np
import trimesh


def digest(path):
    """绑定本次实际保存对象与原生检查记录。"""
    return hashlib.sha256(path.read_bytes()).hexdigest()


here = Path(__file__).parent
diag_path = here/'16-第十五刀保存拒绝面几何来源诊断.json'
diagnosis = json.loads(diag_path.read_text('utf8'))
study = Path('D:/GraduationProject_切削排斥证据/20261006_Geogram共享边竞争生成真实CT连续验证')
rp = study/'真实CT完整父反馈结果/01-真实CT十六刀完整父反馈记录.json'
assert digest(rp) == diagnosis['source_record_sha256']
record = json.loads(rp.read_text('utf8'))
event = record['routes'][0]['events'][14]
generation = Path(event['parent_path']).parents[2]/'event_14/generation'
trace_path = generation/'01-冻结机制执行记录.json'
assert digest(trace_path) == diagnosis['generation_trace_sha256']
trace = json.loads(trace_path.read_text('utf8'))
last = trace['sliver_repair']['flips'][-1]['trial']
initial, accepted = generation/'initial.obj', generation/('repair_'+last+'.obj')
assert digest(initial) == diagnosis['initial_obj_sha256']
mesh, trial_mesh = [trimesh.load(p, process=False) for p in (initial, accepted)]
assert np.array_equal(mesh.vertices, trial_mesh.vertices) and np.array_equal(mesh.faces, trial_mesh.faces)
assert json.loads((generation/'initial_labels.json').read_text('utf8')) == json.loads(accepted.with_name(accepted.stem+'_labels.json').read_text('utf8'))
audit_path = accepted.with_name(accepted.stem+'_audit.json')
audit = json.loads(audit_path.read_text('utf8'))
assert audit['execution']['returncode'] == 0 and audit['embedded_closed']
assert accepted.name in audit['execution']['command']
assert json.loads(audit['execution']['stdout']) == {k: v for k, v in audit.items() if k != 'execution'}
assert diagnosis['rows'][0]['finite_coordinates'] and not diagnosis['rows'][0]['exact_cross_product_zero']
stamp = datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
out = here/'18-拒绝初始面与已接受翻边对象一致性复核.json'
assert not out.exists()
out.write_text(json.dumps({'生成时间': stamp, '修改时间及修改内容': '首次绑定拒绝初始对象与已有精确检查通过对象',
    '文档概述': '有限正面积面低于冻结数值门槛；不改变原拒绝或声称该门槛可以直接取消',
    '索引目录': ['files'], 'status': 'completed_rejected_initial_equals_exactly_checked_accepted_flip_object',
    'diagnosis_sha256': digest(diag_path), 'source_record_sha256': digest(rp),
    'vertices_faces_labels_equal': True, 'prior_native_embedded_closed': True,
    'new_native_calls': 0, 'new_generation_calls': 0, 'GPU_calls': 0,
    'files': [{'path': str(p), 'sha256': digest(p)} for p in (initial, accepted, audit_path, Path(__file__))]},
    ensure_ascii=False, indent=2)+'\n', 'utf8')
print('拒绝初始对象与既有精确检查通过对象逐数组一致；原拒绝不变', flush=True)
