"""每刀仅反馈本内核的实际有效输出，任何拒绝阻断后缀并保留16事件分母。"""
from pathlib import Path
from datetime import datetime,timezone,timedelta
import hashlib
import json
import os
import random
import subprocess
import time
import zipfile

root=Path(__file__).resolve().parent
folder=root/'native_ct16_feedback_01';folder.mkdir()
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
now=lambda:datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
build=json.loads((root/'build_record.json').read_text('utf8'))
manifest=json.loads((root/'ct16_manifest.json').read_text('utf8'))
assert build['status']=='completed_candidate_build_with_verified_original_baseline_reuse'
assert sha(root/'build_record.json')==manifest['candidate_build_sha256']
assert sha(root/'source_manifest.json')==manifest['candidate_manifest_sha256']
for method in ['baseline','candidate']:assert sha(root/method)==build[method+'_binary_sha256']
diagnosis=Path('/root/autodl-tmp/graduation_project/constrained_累计工具与参照完整定位_4eb45179119c/diagnosis')
assert sha(diagnosis)=='0288aa598c3a0284b12ce55f73d6ee3d1fa5d290f43ac0aefc890f56aae5d7cd'
os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:4])
os.environ.pop('GEO_NATIVE_QUALITY_TRACE',None)
record={'生成时间':now(),'修改时间及修改内容':'首次从原初态运行本原生内核反馈路线',
        '文档概述':'不接外部维护；每刀原版参照使用候选同父输入，不是独立原版反馈路线',
        '索引目录':['preflight','events'],'status':'running','planned_events':16,
        'manifest_sha256':sha(root/'ct16_manifest.json'),'build_sha256':sha(root/'build_record.json'),
        'affinity':sorted(os.sched_getaffinity(0)),'preflight':[],'events':[]}
path=folder/'01-原生CT十六刀反馈实际记录.json'
def save():
    """实际事件完成后原子写入，拒绝与受阻均不修改为发布。"""
    temporary=path.with_suffix('.tmp');temporary.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n','utf8');temporary.replace(path)

def audit(mesh,label):
    """全量准确检查与同一保存对象摘要绑定，不用闭合布尔值代替自交检查。"""
    p=subprocess.run([str(diagnosis),str(mesh)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=60)
    result={'returncode':p.returncode,'stdout':p.stdout,'stderr':p.stderr,'mesh_sha256':sha(mesh)}
    output=folder/(label+'_audit.json');output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n','utf8')
    valid=p.returncode==0 and bool(json.loads(p.stdout)['embedded_closed'])
    return {'path':str(output),'sha256':sha(output),'embedded_closed':valid,'mesh_sha256':sha(mesh)}

def native_run(method,parent,tool,index):
    """保存原生返回对象及实际内核计时，超时明确计失败。"""
    output=folder/f'e{index:02d}_{method}.obj';log=folder/f'e{index:02d}_{method}.log'
    start=time.perf_counter()
    try:
        p=subprocess.run([str(root/method),str(parent),str(tool),str(output)],
                         stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=30)
    except subprocess.TimeoutExpired as error:
        partial=error.stdout or ''
        if isinstance(partial,bytes):partial=partial.decode('utf8',errors='replace')
        p=subprocess.CompletedProcess(error.cmd,124,partial+'\nNATIVE_RESEARCH_TIMEOUT seconds=30\n')
    log.write_text(p.stdout,'utf8')
    result={'returncode':p.returncode,'log_sha256':sha(log),'subprocess_wall_ms':(time.perf_counter()-start)*1000}
    if p.returncode==0:
        result.update(mesh_path=str(output),mesh_sha256=sha(output),
                      native_timing=json.loads(next(s[len('NATIVE_RESULT '):] for s in p.stdout.splitlines() if s.startswith('NATIVE_RESULT '))),
                      audit=audit(output,f'e{index:02d}_{method}'))
    return result

save()
try:
    initial=root/'ct16_inputs'/manifest['initial']['file'];assert sha(initial)==manifest['initial']['sha256']
    objects=[('initial',initial)]+[(f"tool{i:02d}",root/'ct16_inputs'/tool['file']) for i,tool in enumerate(manifest['tools'])]
    for label,mesh in objects:
        if label!='initial':assert sha(mesh)==manifest['tools'][int(label[4:])]['sha256']
        checked=audit(mesh,label);record['preflight'].append({'object':label,'audit':checked});save()
        assert checked['embedded_closed']
    parent=initial;blocked=False;rng=random.Random(2026100601)
    for i,tool in enumerate(manifest['tools']):
        row={'event_index':i,'event_id':tool['event_id'],'tool_sha256':tool['sha256']}
        if blocked:
            row['status']='blocked_by_preceding_rejection';record['events'].append(row);save();continue
        row.update(parent_path=str(parent),parent_sha256=sha(parent),methods={})
        order=['baseline','candidate'];rng.shuffle(order)
        for method in order:row['methods'][method]=native_run(method,parent,root/'ct16_inputs'/tool['file'],i)
        candidate=row['methods']['candidate']
        valid=candidate['returncode']==0 and candidate['audit']['embedded_closed']
        row['status']='accepted_native_output' if valid else 'rejected_native_output'
        record['events'].append(row);save()
        print('event',i,row['status'],candidate.get('native_timing',{}).get('boolean_ms'),flush=True)
        if valid:parent=Path(candidate['mesh_path'])
        else:blocked=True
    assert len(record['events'])==16
    record.update(status='completed_all_planned_events_with_rejections' if blocked else 'completed_sixteen_native_candidate_feedback_events',finished_beijing=now())
    save()
except BaseException as error:
    record.update(status='failed_actual_native_feedback_controller',error=str(error),finished_beijing=now());save();raise
finally:
    with zipfile.ZipFile(root/'native_ct16_feedback_01.zip','x',compression=zipfile.ZIP_DEFLATED,compresslevel=3) as archive:
        for p in folder.iterdir():archive.write(p,p.name)
