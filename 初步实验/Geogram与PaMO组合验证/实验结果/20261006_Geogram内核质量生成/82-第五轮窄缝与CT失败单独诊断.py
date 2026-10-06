"""整轮真实失败后单独保存两窄缝轨迹和CT崩溃轨迹，不补写原批次。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import importlib.util
import json
import shlex

here=Path(__file__).resolve().parent
folder=here/'共享边候选失败后单独诊断';folder.mkdir()
spec=importlib.util.spec_from_file_location('native_remote',here/'01-隔离内核研究远程入口.py')
remote=importlib.util.module_from_spec(spec);spec.loader.exec_module(remote)
root='/tmp/geogram_native_quality_20261006_06'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
now=lambda:datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
record={'生成时间':now(),'修改时间及修改内容':'整批失败后另行诊断，不修改原142尝试记录',
        '文档概述':'两窄缝拒绝及CT崩溃轨迹，非速度测量',
        '索引目录':['rows'],'status':'running','rows':[],
        'candidate_binary_sha256':json.loads((here/'73-第五轮实际原生编译记录.json').read_text('utf8'))['candidate_binary_sha256']}
path=folder/'01-整批失败后单独生成诊断记录.json'
def save():
    """单项实际退出码、日志与输出各自保存。"""
    path.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n','utf8')
save();client=remote.connect()
try:
    _,out,_=client.exec_command('mkdir '+root+'/post_failure_diagnosis');assert out.channel.recv_exit_status()==0
    with client.open_sftp() as sftp:
        for i in [5,6,10]:
            command='GEO_NATIVE_QUALITY_TRACE=1 '+shlex.join([root+'/candidate',root+f'/inputs/{i:02d}_parent.obj',
                       root+f'/inputs/{i:02d}_tool.obj',root+f'/post_failure_diagnosis/{i:02d}.obj'])
            _,out,_=client.exec_command(command);out.channel.set_combine_stderr(True)
            content=out.read().decode('utf8','replace');rc=out.channel.recv_exit_status()
            log=folder/f'{i:02d}-实际生成日志.txt';log.write_text(content,'utf8')
            traces=[json.loads(line[len('NATIVE_QUALITY_REGION '):]) for line in content.splitlines()
                    if line.startswith('NATIVE_QUALITY_REGION ')]
            row={'case_index':i,'returncode':rc,'log_sha256':sha(log),'regions':traces,
                 'whole_quality_log':[line for line in content.splitlines() if 'shared_edges=' in line]}
            if rc==0:
                output=folder/f'{i:02d}-实际输出.obj';sftp.get(root+f'/post_failure_diagnosis/{i:02d}.obj',str(output))
                row['mesh_sha256']=sha(output)
            record['rows'].append(row);save();print(i,rc,len(traces),row['whole_quality_log'],flush=True)
    record.update(status='completed_three_separate_actual_attempt_diagnoses',finished_beijing=now());save()
except BaseException as error:
    record.update(status='failed_actual_post_failure_diagnosis',error=str(error),finished_beijing=now());save();raise
finally:
    client.close()
