"""同机顺序CPU/CUDA预算实验，保存真实终态及故障分母。"""
from datetime import datetime,timezone,timedelta
import json
import os
from pathlib import Path
import subprocess
import sys

root=Path(__file__).resolve().parent
checker='/root/autodl-tmp/graduation_project/exact_mesh_audit_20261004_0646'
rows=[]
def save(status):
    temporary=root/'controller.tmp'
    temporary.write_text(json.dumps(dict(time_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat(),status=status,pid=os.getpid(),rows=rows),indent=2))
    temporary.replace(root/'controller.json')
save('running')
for backend in ('cpu','cuda'):
    with (root/(backend+'_controller.log')).open('w') as log:
        try:
            result=subprocess.run([sys.executable,str(root/'benchmark.py'),'--root',str(root),'--backend',backend,'--checker',checker],
                stdout=log,stderr=subprocess.STDOUT,timeout=900)
            rows.append(dict(backend=backend,returncode=result.returncode))
        except subprocess.TimeoutExpired:
            rows.append(dict(backend=backend,returncode='timeout'))
    save('running')
save('completed_with_recorded_outcomes')
