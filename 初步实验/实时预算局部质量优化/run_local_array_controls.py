"""在独立本机目录绑定新旧DLL，核对拓扑与近接触控制，不修改正式加载路径。"""
from pathlib import Path
import datetime
import hashlib
import json
import os
import shutil
import subprocess
import sys

BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[1]/'tmp/数组源证书本机控制_20261006_v2'
BUILD=BASE.parents[1]/'tmp/数组源证书本机编译/Release'
ROOT.mkdir(exist_ok=False)
report=dict(time_beijing=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
    status='running',stages=[],platform='Windows',scope='本机同配置控制，不替代Linux CUDA反馈或实际显示计时')
target=ROOT/'01-本机数组源证书执行记录.json'


def save():
    temporary=target.with_suffix('.tmp')
    temporary.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');temporary.replace(target)


save()
try:
    wrapper=(BASE/'incremental_mesh_memory.py').read_text(encoding='utf-8')
    begin=wrapper.index('        # 相同原生证书')
    end=wrapper.index('        self.lib=C.CDLL',begin)
    wrapper=wrapper[:begin]+"        # 本机私有控制仅从工作器旁加载独立编译DLL。\n        path=Path(__file__).with_name('incremental_mesh_memory.dll')\n"+wrapper[end:]
    for name,library in [('workers','incremental_mesh_memory.dll'),('reference_workers','incremental_mesh_reference.dll')]:
        current=ROOT/name;current.mkdir()
        (current/'incremental_mesh_memory.py').write_text(wrapper,encoding='utf-8')
        shutil.copyfile(BUILD/library,current/'incremental_mesh_memory.dll')
    report['libraries']={name:hashlib.sha256((ROOT/name/'incremental_mesh_memory.dll').read_bytes()).hexdigest()
                         for name in ['workers','reference_workers']}
    report['sources']={name:hashlib.sha256((BASE/name).read_bytes()).hexdigest() for name in
                       ['incremental_mesh_memory_array.cpp','incremental_mesh_memory_filtered.cpp','verify_array_topology.py','verify_filtered_mesh_controls.py']}
    environment=dict(os.environ,PYTHONPATH=str(ROOT/'workers')+os.pathsep+str(BASE))
    for name in ['verify_array_topology.py','verify_filtered_mesh_controls.py']:
        shutil.copyfile(BASE/name,ROOT/'workers'/name)
        log=ROOT/(name+'.log')
        with log.open('x',encoding='utf-8') as stream:
            code=subprocess.run([sys.executable,str(ROOT/'workers'/name),'--root',str(ROOT)],
                                env=environment,stdout=stream,stderr=subprocess.STDOUT).returncode
        report['stages'].append(dict(name=name,returncode=code,log_sha256=hashlib.sha256(log.read_bytes()).hexdigest()));save()
        assert code==0,(name,code)
    report['status']='completed';save()
except Exception as error:
    report.update(status='failed',error=repr(error));save();raise
print(json.dumps(dict(status=report['status'],stages=report['stages'])),flush=True)
