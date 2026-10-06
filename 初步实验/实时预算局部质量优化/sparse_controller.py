"""实际顺序运行两个后端，保留部分记录、退出原因与进程身份。"""
from datetime import datetime,timezone,timedelta
import json
import os
from pathlib import Path
import subprocess
import sys

root=Path(__file__).resolve().parent
entry=json.loads((root/'02-输入与研究预算冻结.json').read_text(encoding='utf-8'))['protocol'].get('benchmark_entry','benchmark_sparse.py')
checker='/root/autodl-tmp/graduation_project/exact_mesh_audit_20261004_0646'
rows=[]
def save(status):
    temporary=root/'controller.tmp'
    temporary.write_text(json.dumps(dict(time_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat(),status=status,pid=os.getpid(),rows=rows),indent=2),encoding='utf-8')
    temporary.replace(root/'controller.json')
save('running')
for backend in ('cpu','cuda'):
    with (root/(backend+'_controller.log')).open('w') as log:
        try:
            # 执行冻结清单指定的真实入口，不能把不同计时边界的批次混为一个方法。
            result=subprocess.run([sys.executable,str(root/entry),'--root',str(root),'--backend',backend,'--checker',checker],stdout=log,stderr=subprocess.STDOUT,timeout=1200)
            rows.append(dict(backend=backend,returncode=result.returncode))
        except subprocess.TimeoutExpired:
            rows.append(dict(backend=backend,returncode='timeout'))
    save('running')
save('completed_with_recorded_outcomes')
