"""保留首次编码失败，核对已恢复对象后只修订控制器UTF-8读取并复跑组件对照。"""
from pathlib import Path
import datetime
import hashlib
import json
import os
import subprocess
import sys

BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[1]/'tmp/数组源证书本机控制_20261006'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
binding=ROOT/'08-实际对象恢复与本机配对绑定.json'
old=json.loads(binding.read_text(encoding='utf-8'));assert old['status']=='failed'
assert sha(ROOT/'component_96_pairs.log')==old['log_sha256']
for row in old['objects']:
    p=ROOT/'frozen_feedback'/row['member'];assert p.stat().st_size==row['size'] and sha(p)==row['sha256']
original=ROOT/'workers/verify_cached_source_certificate.py'
script=original.read_text(encoding='utf-8').replace('.read_text()',".read_text(encoding='utf-8')")
# 上次配对完成后在参照库摘要处仍使用Linux文件名；本次只修正报告绑定文件名。
script=script.replace('libincremental_mesh_memory.so','incremental_mesh_memory.dll')
script=script.replace("    target=root/'02-缓存", "    result['actual_control_source_sha256']=sha(Path(__file__))\n    target=root/'02-缓存")
current=ROOT/'workers/verify_cached_source_certificate_utf8_windows.py';assert not current.exists()
current.write_text(script,encoding='utf-8')
env=dict(os.environ,PYTHONPATH=str(ROOT/'workers')+os.pathsep+str(BASE))
log=ROOT/'component_96_pairs_utf8_windows.log'
with log.open('x',encoding='utf-8') as stream:
    code=subprocess.run([sys.executable,str(current),'--root',str(ROOT),
        '--batch',str(ROOT/'frozen_feedback/tmp/geogram_unique_facets_20261006_flat/r0_flat'),
        '--initial',str(ROOT/'frozen_feedback/tmp/geogram_certified_pairs_20261006_r3/inputs/initial.obj')],
        env=env,stdout=stream,stderr=subprocess.STDOUT).returncode
target=ROOT/'10-UTF8与库文件名修订实际组件执行记录.json';assert not target.exists()
report=dict(time_beijing=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
    status='completed' if code==0 else 'failed',returncode=code,first_binding_sha256=sha(binding),
    first_log_sha256=old['log_sha256'],previous_failed_resume_sha256=sha(ROOT/'09-UTF8修订实际组件执行记录.json'),
    actual_control_source_sha256=sha(current),log_sha256=sha(log),
    component_report_sha256=sha(ROOT/'02-缓存精确源证书九十六配对完整核对.json') if code==0 else None)
target.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
assert code==0,code
print(json.dumps(report),flush=True)
