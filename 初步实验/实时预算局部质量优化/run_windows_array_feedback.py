"""同一私有快速Geogram内核上交错比较原源证书与数组证书，完整CPU反馈及本机像素另计。"""
from pathlib import Path
import datetime
import hashlib
import json
import os
import shutil
import subprocess
import sys

BASE=Path(__file__).resolve().parent
ROOT=Path('D:/GraduationProject实验输出/20261007_数组源证书本机完整反馈')
PREP=ROOT/'03-平台宏与UTF8完整私有构建.json'
prepared=json.loads(PREP.read_text(encoding='utf-8'));assert prepared['status']=='completed'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
for name,digest in prepared['frozen_files'].items():assert sha(ROOT/name)==digest
workers=ROOT/'workers'
for name in ['verify_array_topology.py','verify_filtered_mesh_controls.py','verify_cached_source_certificate.py','verify_fixed_flip_certificate.py']:
    shutil.copyfile(BASE/name,workers/name)
path=workers/'verify_cached_source_certificate.py'
text=path.read_text(encoding='utf-8').replace('libincremental_mesh_memory.so','incremental_mesh_memory.dll')
path.write_text(text,encoding='utf-8')
for name in ['workers','reference_workers']:
    path=ROOT/name/'render_live_gpu_feedback.py';text=path.read_text(encoding='utf-8')
    assert "'--edge-backend','cuda'" in text
    # 本机CPU维护与实际显示分别记录；不把它标作远端CUDA维护或NVIDIA渲染验证。
    text=text.replace("'--edge-backend','cuda'","'--edge-backend','cpu'")
    text=text.replace("        budget_ms=args.budget,frames=frames", "        maintenance_backend='cpu',platform='Windows',budget_ms=args.budget,frames=frames")
    path.write_text(text,encoding='utf-8')
record=ROOT/'04-本机CPU完整四预算与像素执行记录.json';assert not record.exists()
report=dict(time_beijing=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
    status='running',platform='Windows',edge_backend='cpu',prepared_sha256=sha(PREP),stages=[],trials=[],renders=[],
    planned_feedback_events=384,resource_isolation_not_proven=True,
    frozen_files={str(p.relative_to(ROOT)):sha(p) for name in ['workers','reference_workers'] for p in (ROOT/name).iterdir() if p.is_file()},
    scope='已见CT16真实父链，本机CPU整链与实际帧缓冲，未运行远端新CUDA版本')
environment=dict(os.environ,PYTHONUTF8='1')
ct=ROOT/'inputs/ct_record.json'


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
    component_input=BASE.parents[1]/'tmp/数组源证书本机控制_20261006_v2/frozen_feedback'
    execute('same_parent_96_pairs',[sys.executable,str(workers/'verify_cached_source_certificate.py'),
        '--root',str(ROOT),'--batch',str(component_input/'tmp/geogram_unique_facets_20261006_flat/r0_flat'),
        '--initial',str(component_input/'tmp/geogram_certified_pairs_20261006_r3/inputs/initial.obj')],workers)
    execute('array_topology_controls',[sys.executable,str(workers/'verify_array_topology.py'),'--root',str(ROOT)],workers)
    execute('near_contact_controls',[sys.executable,str(workers/'verify_filtered_mesh_controls.py'),'--root',str(ROOT)],workers)
    execute('fixed_flip_controls',[sys.executable,str(workers/'verify_fixed_flip_certificate.py'),
        '--batch',str(component_input/'tmp/geogram_unique_facets_20261006_flat/r0_flat'),
        '--output',str(ROOT/'08-本机原翻边协议与完整检查.json')],workers)
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
