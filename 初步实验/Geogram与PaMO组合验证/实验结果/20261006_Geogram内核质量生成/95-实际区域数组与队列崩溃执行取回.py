"""在独立诊断版本上捕获两窄缝与CT实际输入，失败调用也完整归档。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import importlib.util
import json
import shlex
import zipfile

here=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('native_remote',here/'01-隔离内核研究远程入口.py')
remote=importlib.util.module_from_spec(spec);spec.loader.exec_module(remote)
root='/tmp/geogram_native_quality_20261006_07'
receipt=here/'96-实际区域输入捕获执行记录.json';assert not receipt.exists()
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
now=lambda:datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
record={'生成时间':now(),'修改时间及修改内容':'首次实际区域输入与非法队列捕获',
        '文档概述':'诊断调用不计速度；异常退出不称有效输出','索引目录':['status'],
        'status':'running','remote':root,'source_manifest_sha256':sha(here/'89-实际Triangle输入与队列诊断源码清单.json')}
def save():
    """控制器仅依据实际执行和取回结果更新状态。"""
    receipt.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n','utf8')
save()
worker=r'''from pathlib import Path
import os,sys,json,subprocess,hashlib,zipfile
from datetime import datetime,timezone,timedelta
root=Path(sys.argv[1]);folder=root/'actual_input_capture';folder.mkdir()
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
now=lambda:datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
build=json.loads((root/'build_record.json').read_text('utf8'));assert build['status']=='completed_candidate_build_with_verified_original_baseline_reuse'
assert sha(root/'candidate')==build['candidate_binary_sha256']
os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:4])
record={'generated_beijing':now(),'status':'running','rows':[],'binary_sha256':sha(root/'candidate')}
path=folder/'01-actual_capture_record.json'
for i in [5,6,10]:
    case=folder/f'{i:02d}';case.mkdir();capture=case/'input_arrays';capture.mkdir()
    mesh=case/'output.obj';env=dict(os.environ,GEO_NATIVE_QUALITY_TRACE='1',GEO_NATIVE_QUALITY_CAPTURE_DIR=str(capture))
    p=subprocess.run([str(root/'candidate'),str(root/'inputs'/f'{i:02d}_parent.obj'),str(root/'inputs'/f'{i:02d}_tool.obj'),str(mesh)],
                     stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,env=env)
    log=case/'actual.log';log.write_text(p.stdout,'utf8')
    row={'case_index':i,'returncode':p.returncode,'log_sha256':sha(log),
         'captured_inputs':{p.name:sha(p) for p in capture.iterdir()},
         'queue_failure_lines':[line for line in p.stdout.splitlines() if line.startswith('TRIANGLE_QUEUE_')]}
    if p.returncode==0:row['mesh_sha256']=sha(mesh)
    record['rows'].append(row);path.write_text(json.dumps(record,indent=2)+'\n','utf8')
    print(i,p.returncode,len(row['captured_inputs']),row['queue_failure_lines'],flush=True)
record.update(status='completed_three_actual_input_captures',finished_beijing=now());path.write_text(json.dumps(record,indent=2)+'\n','utf8')
with zipfile.ZipFile(root/'actual_input_capture.zip','x',compression=zipfile.ZIP_DEFLATED) as z:
    for p in folder.rglob('*'):
        if p.is_file():z.write(p,p.relative_to(folder))
'''
client=remote.connect()
try:
    inp,out,_=client.exec_command('/root/miniconda3/bin/python - '+shlex.quote(root));out.channel.set_combine_stderr(True)
    inp.write(worker);inp.flush();inp.channel.shutdown_write()
    with (here/'97-实际区域捕获控制台日志.txt').open('x',encoding='utf8') as log:
        for line in out:log.write(line);log.flush();print(line,end='',flush=True)
    record['returncode']=out.channel.recv_exit_status();save()
    with client.open_sftp() as sftp:
        archive=here/'98-实际区域数组与队列失败捕获.zip';sftp.get(root+'/actual_input_capture.zip',str(archive))
    record['archive_sha256']=sha(archive)
    folder=here/'实际Triangle输入与非法队列捕获';folder.mkdir()
    with zipfile.ZipFile(archive) as z:
        for n in z.namelist():assert (folder/n).resolve().is_relative_to(folder.resolve())
        z.extractall(folder)
    record.update(status='completed_actual_input_capture_retrieved',finished_beijing=now());save()
    assert record['returncode']==0
except BaseException as error:
    record.update(status='failed_actual_input_capture_controller',error=str(error),finished_beijing=now());save();raise
finally:
    client.close()
