"""核对数组翻边的完整协议负例与连续1024次固定点拓扑事务，不冒称连续磨削。"""
from pathlib import Path
import datetime
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import numpy as np
import trimesh

BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[1]/'tmp/数组源证书本机控制_20261006_v2'
sys.path.insert(0,str(BASE));sys.path.insert(0,str(ROOT/'workers'))
from incremental_mesh_memory import VerifiedMesh
from exact_mesh_memory import ExactMeshMemory

assert json.loads((ROOT/'08-实际对象恢复与本机配对绑定.json').read_text(encoding='utf-8'))['status']=='completed'
script=(BASE/'verify_fixed_flip_certificate.py').read_text(encoding='utf-8')
current=ROOT/'workers/verify_fixed_flip_certificate.py'
if current.exists():assert current.read_text(encoding='utf-8')==script
else:current.write_text(script,encoding='utf-8')
output=ROOT/'11-数组翻边原协议负例与全量核对.json'
env=dict(os.environ,PYTHONPATH=str(ROOT/'workers')+os.pathsep+str(BASE))
log=ROOT/'fixed_flip_protocol.log'
# 编码修订后保留已完成的协议文件与日志，不覆盖或重复执行原48配对。
if not output.exists():
    with log.open('x',encoding='utf-8') as stream:
        code=subprocess.run([sys.executable,str(current),'--batch',str(ROOT/'frozen_feedback/tmp/geogram_unique_facets_20261006_flat/r0_flat'),
                             '--output',str(output)],env=env,stdout=stream,stderr=subprocess.STDOUT).returncode
    assert code==0,code
protocol=json.loads(output.read_text(encoding='utf-8'))
assert protocol['status']=='completed' and protocol['paired_runs']==48 and protocol['protocol_controls']==6
assert protocol['method_sha256'][current.name]==hashlib.sha256(current.read_bytes()).hexdigest()
spec=importlib.util.spec_from_file_location('array_repeated_flip_reference',ROOT/'reference_workers/incremental_mesh_memory.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
full=ExactMeshMemory();old,new=module.VerifiedMesh(),VerifiedMesh()
box=trimesh.creation.box(extents=[2.,2.,2.]);v,f=np.asarray(box.vertices),np.asarray(box.faces).copy()
assert old.check(v,f,True)['embedded_closed'] and new.check(v,f,True)['embedded_closed']
owners=next((i,j) for i in range(len(f)) for j in range(i+1,len(f))
            if len(set(f[i])&set(f[j]))==2 and np.dot(box.face_normals[i],box.face_normals[j])>.999)
rows=[]
for batch in range(64):
    operations=[]
    for step in range(16):
        i,j=owners;before=f[[i,j]].copy()
        a,b,c,d=next((before[0,k],before[0,(k+1)%3],before[0,(k+2)%3],before[1,(t+2)%3])
            for k in range(3) for t in range(3)
            if before[0,k]==before[1,(t+1)%3] and before[0,(k+1)%3]==before[1,t])
        after=np.array([[c,d,b],[d,c,a]],dtype=np.int64)
        operations.append(dict(faces=list(owners),before=before.tolist(),after=after.tolist()));f[[i,j]]=after
    # 同一实际数组分别提交；任何一次拒绝都终止，不把回滚冒充成功。
    x,y=old.check_flips(v,f,operations),new.check_flips(v,f,operations);z=full.audit(v,f)
    assert x['embedded_closed'] and y['embedded_closed'] and z['embedded_closed']
    assert all(x[k]==y[k] for k in ['verified_operations','exact_pairs_checked','rejection_code'])
    inherited_old,inherited_new=old.check(v,f),new.check(v,f)
    assert inherited_old['inherited_faces']==inherited_new['inherited_faces']==len(f)
    rows.append(dict(batch=batch,reference=x,array=y,full=z,operations=operations,
                     final_faces_sha256=hashlib.sha256(f.tobytes()).hexdigest()))
old.close();new.close()
target=ROOT/'12-连续数组翻边1024操作与父继承控制.json';assert not target.exists()
report=dict(time_beijing=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
    status='completed',batches=64,operations=1024,all_full_checks_embedded=True,rows=rows,
    original_protocol_pairs=48,original_protocol_negative_controls=6,protocol_report_sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
    actual_control_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    scope='小闭盒上重复合法翻边和完整父继承控制，不是1024次材料去除或长期独立输入稳定性证明')
target.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(status='completed',protocol_pairs=48,negative_controls=6,batches=64,operations=1024)),flush=True)
