"""原版从同初态使用自己的有效父输出，失败后保留完整16事件受阻分母。"""
from pathlib import Path
from datetime import datetime,timezone,timedelta
import hashlib
import json
import os
import subprocess
import zipfile

root=Path('/tmp/geogram_native_quality_20261006_21')
folder=root/'original_ct16_independent_feedback_01';folder.mkdir()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
now=lambda:datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
build=json.loads((root/'build_record.json').read_text('utf8'))
manifest=json.loads((root/'ct16_manifest.json').read_text('utf8'))
assert sha(root/'baseline')==build['baseline_binary_sha256']
checker=Path('/root/autodl-tmp/graduation_project/constrained_累计工具与参照完整定位_4eb45179119c/diagnosis')
assert sha(checker)=='0288aa598c3a0284b12ce55f73d6ee3d1fa5d290f43ac0aefc890f56aae5d7cd'
initial=root/'ct16_inputs'/manifest['initial']['file'];assert sha(initial)==manifest['initial']['sha256']
os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:4])
os.environ.pop('GEO_NATIVE_QUALITY_TRACE',None)
record={'生成时间':now(),'修改时间及修改内容':'首次原版独立实际父反馈路线',
 '文档概述':'初态和16工具与候选一致；后续父使用原版自身，不据不同有效子集比较速度',
 '索引目录':['events'],'status':'running','planned_events':16,'initial_sha256':sha(initial),
 'binary_sha256':sha(root/'baseline'),'manifest_sha256':sha(root/'ct16_manifest.json'),
 'checker_sha256':sha(checker),'events':[]}
path=folder/'01-原版独立十六刀实际父反馈记录.json'
def save():
    """发布、拒绝、受阻全部保留，执行结束不能误称路线完成。"""
    temporary=path.with_suffix('.tmp');temporary.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n','utf8');temporary.replace(path)
save();parent=initial;blocked=False
try:
    for i,tool in enumerate(manifest['tools']):
        row={'event_index':i,'event_id':tool['event_id'],'tool_sha256':tool['sha256']}
        tool_path=root/'ct16_inputs'/tool['file'];assert sha(tool_path)==tool['sha256']
        if blocked:
            row['status']='blocked_by_preceding_rejection';record['events'].append(row);save();continue
        mesh=folder/f'e{i:02d}_baseline.obj';log=folder/f'e{i:02d}_baseline.log'
        row.update(parent_sha256=sha(parent),parent_path=str(parent))
        try:
            p=subprocess.run([str(root/'baseline'),str(parent),str(tool_path),str(mesh)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=30)
        except subprocess.TimeoutExpired as error:
            partial=error.stdout or ''
            if isinstance(partial,bytes):partial=partial.decode('utf8',errors='replace')
            p=subprocess.CompletedProcess(error.cmd,124,partial+'\nNATIVE_RESEARCH_TIMEOUT seconds=30\n')
        log.write_text(p.stdout,'utf8');row.update(returncode=p.returncode,log_sha256=sha(log))
        valid=False
        if p.returncode==0:
            row.update(mesh_sha256=sha(mesh),mesh_path=str(mesh),native_timing=json.loads(next(line[len('NATIVE_RESULT '):] for line in p.stdout.splitlines() if line.startswith('NATIVE_RESULT '))))
            p=subprocess.run([str(checker),str(mesh)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=60)
            audit={'returncode':p.returncode,'stdout':p.stdout,'stderr':p.stderr,'mesh_sha256':sha(mesh)}
            ap=folder/f'e{i:02d}_baseline_audit.json';ap.write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n','utf8')
            valid=p.returncode==0 and json.loads(p.stdout)['embedded_closed']
            row.update(audit_sha256=sha(ap),audit_path=str(ap),embedded_closed=valid)
        row['status']='accepted_native_output' if valid else 'rejected_native_output'
        record['events'].append(row);save();print('original_event',i,row['status'],flush=True)
        if valid:parent=mesh
        else:blocked=True
    assert len(record['events'])==16
    record.update(status='completed_all_sixteen_original_events_with_rejections' if blocked else 'completed_sixteen_original_native_feedback_events',finished_beijing=now())
    save()
finally:
    with zipfile.ZipFile(root/'original_ct16_independent_feedback_01.zip','x',compression=zipfile.ZIP_DEFLATED) as archive:
        for p in folder.iterdir():archive.write(p,p.name)
