"""保留首次启动绑定失败，只修正私有DLL文件名，复用已完成控制后新目录执行完整链路。"""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys

BASE=Path(__file__).resolve().parent
ROOT=Path('D:/GraduationProject实验输出/20261007_数组源证书本机完整反馈')
old_path=ROOT/'04-本机CPU完整四预算与像素执行记录.json'
old=json.loads(old_path.read_text(encoding='utf-8'));assert old['status']=='failed'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
for member,digest in old['frozen_files'].items():assert sha(ROOT/member)==digest
assert len(old['stages'])==5 and all(r['returncode']==0 for r in old['stages'][:4])
assert old['stages'][-1]['name']=='feedback_0_reference_workers' and old['stages'][-1]['returncode']==1
assert not (ROOT/'r0_reference_workers/01-真实父反馈四预算完整记录.json').exists()
source=BASE/'run_windows_array_feedback.py';first=ROOT/'run_windows_array_feedback_first_failed.py';assert not first.exists()
first.write_bytes(source.read_bytes())
for name in ['workers','reference_workers']:
    path=ROOT/name/'verified_budget_feedback.py'
    backup=ROOT/f'verified_budget_feedback_{name}_linux_identity.py';backup.write_bytes(path.read_bytes())
    text=path.read_text(encoding='utf-8')
    assert text.count('libshort_edge_scan.so')==1
    # 方法摘要必须绑定实际加载的Windows扫描DLL；不改动短边修复计算。
    text=text.replace('libshort_edge_scan.so','short_edge_scan.dll');path.write_text(text,encoding='utf-8')
script=source.read_text(encoding='utf-8')
script=script.replace('BASE=Path(__file__).resolve().parent',f'BASE=Path({BASE.as_posix()!r})')
begin=script.index('prepared=json.loads(PREP.read_text');end=script.index("record=ROOT/'04-",begin)
script=script[:begin]+"sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()\nworkers=ROOT/'workers'\n"+script[end:]
script=script.replace('04-本机CPU完整四预算与像素执行记录.json','09-Windows扫描库身份修订完整链路执行记录.json')
begin=script.index('    component_input=BASE.parents');end=script.index('    for repeat in range(3):',begin)
script=script[:begin]+script[end:]
script=script.replace("out=ROOT/f'r{repeat}_{name}'","out=ROOT/f'dll_r{repeat}_{name}'")
script=script.replace('def execute(name,argv,current):','def execute(name,argv,current):\n    name="windows_dll_"+name')
current=ROOT/'run_windows_array_feedback_dll_identity.py';assert not current.exists()
current.write_text(script,encoding='utf-8')
log=ROOT/'resume_dll_identity_driver.log'
with log.open('x',encoding='utf-8') as stream:
    code=subprocess.run([sys.executable,str(current)],env=dict(os.environ,PYTHONUTF8='1'),stdout=stream,stderr=subprocess.STDOUT).returncode
assert code==0,code
print(json.dumps(dict(status='completed',first_driver_sha256=sha(old_path),actual_controller_sha256=sha(current))),flush=True)
