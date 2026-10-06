"""已见窄缝负例的新开发修订复核，全部重复与精确检查分别保存。"""
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
old=Path('/tmp/geogram_native_quality_20261007_23')
folder=root/'gap_rejection_probe_02';folder.mkdir()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
now=lambda:datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
build=json.loads((root/'build_record.json').read_text('utf8'))
case=json.loads((old/'native_inputs.json').read_text('utf8'))['cases'][8]
parent=old/'inputs/08_parent.obj';tool=old/'inputs/08_tool.obj'
assert sha(parent)==case['parent_sha256'] and sha(tool)==case['tool_sha256']
for method in ['baseline','candidate']:assert sha(root/method)==build[method+'_binary_sha256']
diagnosis=Path('/root/autodl-tmp/graduation_project/constrained_累计工具与参照完整定位_4eb45179119c/diagnosis')
selected=sorted(os.sched_getaffinity(0))[:4];os.sched_setaffinity(0,selected)
record={'生成时间':now(),'修改时间及修改内容':'首次新开发版本窄缝完整十四调用复核',
 '文档概述':'不属于旧方法独立评价；原旧七次失败保持',
 '索引目录':['rows'],'status':'running','build_sha256':sha(root/'build_record.json'),
 'parent_sha256':sha(parent),'tool_sha256':sha(tool),'diagnosis_sha256':sha(diagnosis),
 'affinity':selected,'planned_attempts':14,'rows':[]}
path=folder/'01-递归新边拒绝窄缝十四调用实际记录.json'
def save():
    """每次实际结果立即落盘，失败不省略。"""
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n','utf8');tmp.replace(path)
save();rng=random.Random(2026100702)
try:
    for repeat in range(-1,6):
        order=['baseline','candidate'];rng.shuffle(order)
        for method in order:
            tag=method+('_warmup' if repeat<0 else f'_r{repeat:02d}')
            mesh=folder/(tag+'.obj');log=folder/(tag+'.log');start=time.perf_counter()
            try:
                process=subprocess.run([str(root/method),str(parent),str(tool),str(mesh)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=30)
            except subprocess.TimeoutExpired as error:
                partial=error.stdout or b''
                if isinstance(partial,bytes):partial=partial.decode('utf8',errors='replace')
                process=subprocess.CompletedProcess([],124,partial+'\nNATIVE_RESEARCH_TIMEOUT seconds=30\n')
            elapsed=(time.perf_counter()-start)*1000;log.write_text(process.stdout,'utf8')
            row={'method':method,'repeat':repeat,'returncode':process.returncode,'subprocess_ms':elapsed,'log_sha256':sha(log)}
            if process.returncode==0:
                line=next(x[len('NATIVE_RESULT '):] for x in process.stdout.splitlines() if x.startswith('NATIVE_RESULT '))
                audit=subprocess.run([str(diagnosis),str(mesh)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=60)
                raw=folder/(tag+'_audit.json');raw.write_text(json.dumps({'returncode':audit.returncode,'stdout':audit.stdout,'stderr':audit.stderr},ensure_ascii=False,indent=2)+'\n','utf8')
                result=json.loads(audit.stdout) if audit.returncode==0 else None
                row.update(native_timing=json.loads(line),mesh_sha256=sha(mesh),audit_sha256=sha(raw),audit=result)
            record['rows'].append(row);save();print(tag,process.returncode,row.get('below_10_faces'),row.get('audit',{}).get('embedded_closed'),flush=True)
    assert len(record['rows'])==14
    record.update(status='completed_all_fourteen_development_probe_attempts',finished_beijing=now(),
        returned_meshes=sum(r['returncode']==0 for r in record['rows']),
        valid_meshes=sum(bool(r.get('audit',{}).get('embedded_closed')) for r in record['rows']))
    save()
except BaseException as error:
    record.update(status='failed_actual_development_probe',error=str(error),finished_beijing=now());save();raise
finally:
    with zipfile.ZipFile(root/'gap_rejection_probe_02.zip','x',compression=zipfile.ZIP_DEFLATED) as archive:
        for p in folder.rglob('*'):
            if p.is_file():archive.write(p,p.relative_to(folder))
