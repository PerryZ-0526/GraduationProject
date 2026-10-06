"""终止确认为本研究的超长候选调用，保留实际账本和信号堆栈，不重启。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import importlib.util
import json

here=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('native_remote',here/'01-隔离内核研究远程入口.py')
remote=importlib.util.module_from_spec(spec);spec.loader.exec_module(remote)
client=remote.connect()
code=r'''import json,os,signal,hashlib,time
from pathlib import Path
root=Path('/tmp/geogram_native_quality_20261006_09');pid=828665
argv=(Path('/proc')/str(pid)/'cmdline').read_bytes().rstrip(b'\0').split(b'\0');argv=[x.decode() for x in argv]
expected=[str(root/'candidate'),str(root/'inputs/10_parent.obj'),str(root/'inputs/10_tool.obj'),str(root/'paired_development_01/10/candidate_warmup.obj')]
assert argv==expected
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
build=json.loads((root/'build_record.json').read_text('utf8'));assert sha(root/'candidate')==build['candidate_binary_sha256']
stat=(Path('/proc')/str(pid)/'stat').read_text();fields=stat[stat.rindex(')')+2:].split()
cpu_seconds=(int(fields[11])+int(fields[12]))/os.sysconf('SC_CLK_TCK');assert cpu_seconds>300
before={'pid':pid,'argv':argv,'cpu_seconds':cpu_seconds,'start_ticks':fields[19],
 'binary_sha256':sha(root/'candidate'),'reason':'same-input candidate has consumed over 300 CPU seconds while original warmup boolean was about 0.817 seconds; speed objective violated',
 'intervention':'SIGABRT to capture native stack, no restart','record_before_sha256':sha(root/'paired_development_01/01-原生十一同输入交错质量速度记录.json')}
path=root/'overlong_native_call_intervention.json';assert not path.exists();path.write_text(json.dumps(before,indent=2)+'\n','utf8')
assert (Path('/proc')/str(pid)/'cmdline').read_bytes().rstrip(b'\0').split(b'\0')==[x.encode() for x in expected]
os.kill(pid,signal.SIGABRT)
before['signal_sent']=True;path.write_text(json.dumps(before,indent=2)+'\n','utf8');print(json.dumps(before))
'''
try:
    inp,out,_=client.exec_command('/root/miniconda3/bin/python -');out.channel.set_combine_stderr(True)
    inp.write(code);inp.flush();inp.channel.shutdown_write()
    content=out.read().decode('utf8','replace');rc=out.channel.recv_exit_status();assert rc==0
    record=json.loads(content)
    record['核查时间']=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
    record['修改时间及修改内容']='已确认自己的超长原生调用，保留现场后发出SIGABRT，不重启'
    record['文档概述']='速度实际失败的进程干预，不把人为终止冒称自然退出'
    record['索引目录']=['argv','reason','intervention']
    (here/'141-已确认超长候选调用终止记录.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n','utf8')
    print('自己的候选调用已发送SIGABRT，实际累计CPU秒',record['cpu_seconds'],flush=True)
finally:
    client.close()
