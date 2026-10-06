"""针对已证速度失败的同源输入另作短诊断，只取样自己子进程的指令地址。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import importlib.util
import json

here=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('native_remote',here/'01-隔离内核研究远程入口.py')
remote=importlib.util.module_from_spec(spec);spec.loader.exec_module(remote)
client=remote.connect()
code=r'''import os,sys,json,time,subprocess,ctypes,signal,hashlib
from pathlib import Path
from datetime import datetime,timezone,timedelta
root=Path('/tmp/geogram_native_quality_20261006_09');folder=root/'separate_runtime_instruction_diagnosis';folder.mkdir()
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
now=lambda:datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
build=json.loads((root/'build_record.json').read_text('utf8'));assert sha(root/'candidate')==build['candidate_binary_sha256']
fields='r15 r14 r13 r12 rbp rbx r11 r10 r9 r8 rax rcx rdx rsi rdi orig_rax rip cs eflags rsp ss fs_base gs_base ds es fs gs'.split()
class Registers(ctypes.Structure):_fields_=[(s,ctypes.c_ulonglong) for s in fields]
libc=ctypes.CDLL(None,use_errno=True);libc.ptrace.restype=ctypes.c_long;libc.ptrace.argtypes=[ctypes.c_ulong,ctypes.c_ulong,ctypes.c_void_p,ctypes.c_void_p]
argv=[str(root/'candidate'),str(root/'inputs/10_parent.obj'),str(root/'inputs/10_tool.obj'),str(folder/'output.obj')]
record={'generated_beijing':now(),'scope':'separate bounded diagnosis after actual benchmark failure; original batch unchanged',
        'binary_sha256':sha(root/'candidate'),'argv':argv,'samples':[],'errors':[]}
log=folder/'actual.log'
with log.open('x') as stream:
    p=subprocess.Popen(argv,stdout=stream,stderr=subprocess.STDOUT);record['pid']=p.pid;start=time.monotonic()
    try:
        for sample in range(3):
            time.sleep(2)
            if p.poll() is not None:break
            assert (Path('/proc')/str(p.pid)/'cmdline').read_bytes().rstrip(b'\0').split(b'\0')==[x.encode() for x in argv]
            maps=[line.split() for line in (Path('/proc')/str(p.pid)/'maps').read_text().splitlines()]
            tids=[int(t.name) for t in (Path('/proc')/str(p.pid)/'task').iterdir()]
            attached=[]
            try:
                for tid in tids:
                    if libc.ptrace(16,tid,None,None)!=0:
                        record['errors'].append({'sample':sample,'tid':tid,'stage':'attach','errno':ctypes.get_errno()});continue
                    attached.append(tid);deadline=time.monotonic()+1
                    while time.monotonic()<deadline:
                        found,status=os.waitpid(tid,os.WNOHANG|os.WUNTRACED|0x40000000)
                        if found==tid and os.WIFSTOPPED(status):break
                        time.sleep(.005)
                    else:record['errors'].append({'tid':tid,'stage':'stop_timeout'});continue
                    regs=Registers()
                    if libc.ptrace(12,tid,None,ctypes.byref(regs))!=0:
                        record['errors'].append({'tid':tid,'stage':'getregs','errno':ctypes.get_errno()});continue
                    pc=int(regs.rip);mapping=next((m for m in maps if int(m[0].split('-')[0],16)<=pc<int(m[0].split('-')[1],16)),None)
                    item={'sample':sample,'elapsed_seconds':time.monotonic()-start,'tid':tid,'instruction_address':hex(pc)}
                    if mapping and len(mapping)>=6:
                        module=mapping[-1];base=int(mapping[0].split('-')[0],16)-int(mapping[2],16);offset=pc-base
                        item.update(module=module,module_offset=hex(offset))
                        symbols=subprocess.run(['addr2line','-C','-f','-e',module,hex(offset)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
                        item['symbol']=symbols.stdout.strip();item['symbol_returncode']=symbols.returncode
                    record['samples'].append(item)
            finally:
                for tid in reversed(attached):libc.ptrace(17,tid,None,None)
                if p.poll() is None:os.kill(p.pid,signal.SIGCONT)
    finally:
        if p.poll() is None:p.kill();record['diagnostic_intervention']='SIGKILL after three bounded address samples; no benchmark restart'
        record['returncode']=p.wait();record['elapsed_seconds']=time.monotonic()-start
record.update(status='completed_separate_runtime_instruction_samples',finished_beijing=now(),log_sha256=sha(log))
(folder/'record.json').write_text(json.dumps(record,indent=2)+'\n','utf8');print(json.dumps(record))
'''
try:
    inp,out,_=client.exec_command('/root/miniconda3/bin/python -');out.channel.set_combine_stderr(True)
    inp.write(code);inp.flush();inp.channel.shutdown_write()
    content=out.read().decode('utf8','replace');rc=out.channel.recv_exit_status()
    if rc!=0:raise RuntimeError(content)
    record=json.loads(content)
    record['核查时间']=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
    record['修改时间及修改内容']='单独限次原生指令取样；原失败批次保持'
    record['文档概述']='自有子进程诊断，非完整运行或速度成绩'
    record['索引目录']=['samples','errors']
    (here/'145-超长调用独立指令位置取样结果.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n','utf8')
    print('采样',len(record['samples']),'错误',record['errors'],flush=True)
    for item in record['samples']:print(item.get('module',''),item.get('module_offset',''),item.get('symbol',''),flush=True)
finally:
    client.close()
