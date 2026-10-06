"""只读核对特定运行句柄对应的远端工作器与原生子进程，不重启任务。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import importlib.util
import json

here=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('native_remote',here/'01-隔离内核研究远程入口.py')
remote=importlib.util.module_from_spec(spec);spec.loader.exec_module(remote)
client=remote.connect()
code=r'''import json,subprocess
from pathlib import Path
root='/tmp/geogram_native_quality_20261006_09'
p=Path(root)/'paired_development_01/01-原生十一同输入交错质量速度记录.json'
r=json.loads(p.read_text('utf8'))
lines=subprocess.check_output(['ps','-eo','pid,ppid,etime,time,pcpu,args'],text=True).splitlines()
print(json.dumps({'status':r['status'],'rows':len(r['rows']),'last_rows':r['rows'][-3:],
 'matching_processes':[line.strip() for line in lines if root+'/candidate' in line or root+'/benchmark.py' in line]},ensure_ascii=False))
'''
try:
    inp,out,_=client.exec_command('/root/miniconda3/bin/python -');out.channel.set_combine_stderr(True)
    inp.write(code);inp.flush();inp.channel.shutdown_write()
    content=out.read().decode('utf8','replace');rc=out.channel.recv_exit_status()
    assert rc==0
    item=json.loads(content)
    item['核查时间']=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
    folder=here/'第八轮运行中进程核查';folder.mkdir(exist_ok=True)
    n=len(list(folder.glob('*.json')))+1
    (folder/f'{n:02d}-实际进程核查.json').write_text(json.dumps(item,ensure_ascii=False,indent=2)+'\n','utf8')
    print(item['status'],item['rows'],item['last_rows'][-1],item['matching_processes'],flush=True)
finally:
    client.close()
