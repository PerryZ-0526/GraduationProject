"""对已完成原生评价的全部420计划实际返回保存对象作准确静态检查，不新增生成或计时。"""
from pathlib import Path
from datetime import datetime,timezone,timedelta
from concurrent.futures import ThreadPoolExecutor,as_completed
import hashlib
import json
import os
import subprocess
import zipfile

root=Path(__file__).resolve().parent
source=root/'paired_development_01/01-新边拒绝三十已见输入交错质量速度记录.json'
original=json.loads(source.read_text('utf8'))
assert original['status']=='completed_all_thirty_seen_development_planned_attempts'
assert len(original['rows'])==420
returned=[r for r in original['rows'] if r['returncode']==0]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
now=lambda:datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
checker=Path('/root/autodl-tmp/graduation_project/constrained_累计工具与参照完整定位_4eb45179119c/diagnosis')
assert sha(checker)=='0288aa598c3a0284b12ce55f73d6ee3d1fa5d290f43ac0aefc890f56aae5d7cd'
os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:4])
folder=root/'all_saved_repeat_exact_audits_01';folder.mkdir()
record={'生成时间':now(),'修改时间及修改内容':'首次全部420计划保存重复的独立准确核查',
 '文档概述':'静态保存网格核查，不计入既有原生速度；失败保持实际结果',
 '索引目录':['rows','totals'],'status':'running','source_sha256':sha(source),
 'checker_sha256':sha(checker),'planned':len(returned),'planned_attempts':420,'rows':[]}
path=folder/'01-420计划实际保存对象准确复审记录.json'
def save():
    """已完成审计原子保存，不把执行完毕等同于几何全部有效。"""
    temporary=path.with_suffix('.tmp');temporary.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n','utf8');temporary.replace(path)
def check(row):
    """每项前后摘要一致，确保检查对象就是原生成保存网格。"""
    mesh=Path(row['mesh_path']);assert sha(mesh)==row['mesh_sha256']
    p=subprocess.run([str(checker),str(mesh)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=60)
    assert sha(mesh)==row['mesh_sha256']
    result=json.loads(p.stdout) if p.returncode==0 else None
    audit={'case_index':row['case_index'],'method':row['method'],'repeat':row['repeat'],
     'mesh_sha256':row['mesh_sha256'],'returncode':p.returncode,'stdout':p.stdout,'stderr':p.stderr,
     'embedded_closed':bool(result and result['embedded_closed']),
     'self_intersection_pairs':result['self_intersection_pairs'] if result else None}
    tag='warmup' if row['repeat']<0 else 'r'+str(row['repeat']).zfill(2)
    output=folder/(str(row['case_index']).zfill(2)+'_'+row['method']+'_'+tag+'.json')
    output.write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n','utf8')
    audit.update(audit_sha256=sha(output),audit_file=output.name)
    return audit
save()
try:
    with ThreadPoolExecutor(max_workers=4) as pool:
        for future in as_completed([pool.submit(check,row) for row in returned]):
            row=future.result();record['rows'].append(row);save()
            if not row['embedded_closed']:print('invalid_saved_output',row['case_index'],row['method'],row['repeat'],row['self_intersection_pairs'],flush=True)
    assert len(record['rows'])==len(returned)
    record['rows'].sort(key=lambda r:(r['case_index'],r['method'],r['repeat']))
    record.update(status='completed_all_saved_objects_from_420_planned_attempts_exact_audits',finished_beijing=now(),
      totals={m:{'planned_attempts':210,'total':sum(r['method']==m for r in record['rows']),
                  'embedded_closed':sum(r['method']==m and r['embedded_closed'] for r in record['rows'])} for m in ['baseline','candidate']})
    save();print(json.dumps(record['totals']),flush=True)
except BaseException as error:
    record.update(status='failed_all_saved_exact_audit',error=str(error),finished_beijing=now());save();raise
finally:
    with zipfile.ZipFile(root/'all_saved_repeat_exact_audits_01.zip','x',compression=zipfile.ZIP_DEFLATED) as archive:
        for p in folder.iterdir():archive.write(p,p.name)
