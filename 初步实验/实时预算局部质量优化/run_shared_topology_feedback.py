"""原排序与证书邻接复用交错运行完整四预算，实际Arc像素和保存审计分别核对。"""
from pathlib import Path
import datetime
import hashlib
import json
import os
import subprocess
import sys

ROOT=Path('D:/GraduationProject实验输出/20261007_证书邻接复用完整反馈')
OLD=Path('D:/GraduationProject实验输出/20261007_数组源证书本机完整反馈')
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
prepared=json.loads((ROOT/'01-私有邻接复用准备与编译.json').read_text(encoding='utf-8'))
controls=json.loads((ROOT/'02-邻接复用九十六同源与完整提交核对.json').read_text(encoding='utf-8'))
assert prepared['status']==controls['status']=='completed' and controls['pairs']==96
for member,digest in prepared['frozen_files'].items():assert sha(ROOT/member)==digest
record=ROOT/'03-邻接复用完整四预算与像素执行.json';assert not record.exists()
report=dict(time_beijing=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),status='running',
    preparation_sha256=sha(ROOT/'01-私有邻接复用准备与编译.json'),controls_sha256=sha(ROOT/'02-邻接复用九十六同源与完整提交核对.json'),
    stages=[],trials=[],renders=[],planned_feedback_events=384,platform='Windows',maintenance_backend='cpu',
    resource_isolation_not_proven=True,
    frozen_files={str(p.relative_to(ROOT)):sha(p) for name in ['workers','reference_workers'] for p in (ROOT/name).iterdir() if p.is_file()},
    input_record_sha256=sha(OLD/'inputs/ct_record.json'))
environment=dict(os.environ,PYTHONUTF8='1');ct=OLD/'inputs/ct_record.json'


def save():
    temp=record.with_suffix('.tmp');temp.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(record)


def execute(name,argv,current):
    for member,digest in report['frozen_files'].items():assert sha(ROOT/member)==digest
    with (ROOT/(name+'.log')).open('x',encoding='utf-8') as stream:
        code=subprocess.run(argv,cwd=current,env=environment,stdout=stream,stderr=subprocess.STDOUT).returncode
    report['stages'].append(dict(name=name,returncode=code,argv=argv,log_sha256=sha(ROOT/(name+'.log'))));save()
    assert code==0,(name,code)


save()
try:
    for repeat in range(3):
        for name in (['reference_workers','workers'] if repeat%2==0 else ['workers','reference_workers']):
            current=ROOT/name;out=ROOT/f'r{repeat}_{name}'
            trial=dict(repeat=repeat,variant=name,status='running',output=str(out));report['trials'].append(trial);save()
            execute(f'feedback_{repeat}_{name}',[sys.executable,str(current/'verified_budget_feedback.py'),
                '--ct-record',str(ct),'--output',str(out),'--fixed-flip-certificate','--early-quality-return',
                '--edge-backend','cpu','--certified-operand-pairs','--linear-unique-facets'],current)
            execute(f'audit_{repeat}_{name}',[sys.executable,str(current/'audit_verified_budget_feedback.py'),'--root',str(out)],current)
            trial.update(status='completed',record_sha256=sha(out/'01-真实父反馈四预算完整记录.json'),
                audit_sha256=sha(out/'02-完整保存全量精确复审与四预算统计.json'));save()
    for name,budget in [('reference_workers',100),('workers',100),('workers',200)]:
        current=ROOT/name;out=ROOT/f'render_{name}_{budget}'
        execute(f'render_{name}_{budget}',[sys.executable,str(current/'render_live_gpu_feedback.py'),
            '--ct-record',str(ct),'--output',str(out),'--budget',str(budget),'--linear-unique-facets'],current)
        path=out/'01-真实GPU父反馈与像素交付完整记录.json'
        report['renders'].append(dict(variant=name,budget=budget,path=str(path),sha256=sha(path)));save()
    report['status']='completed';save()
except Exception as error:
    report.update(status='failed',error=repr(error));save();raise
print(json.dumps(dict(status='completed',trials=len(report['trials']),renders=len(report['renders']))),flush=True)
