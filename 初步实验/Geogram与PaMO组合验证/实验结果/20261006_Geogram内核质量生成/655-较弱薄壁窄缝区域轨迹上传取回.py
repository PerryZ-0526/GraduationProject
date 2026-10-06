"""保存冻结方法完整定位结果，不修改正式计时或生成参数。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import importlib.util
import json
import zipfile

here=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
now=lambda:datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
root='/tmp/geogram_native_quality_20261007_34'
receipt=here/'656-较弱薄壁窄缝区域诊断实际取回记录.json';assert not receipt.exists()
record={'生成时间':now(),'修改时间及修改内容':'首次较弱输入八次区域诊断实际取回','文档概述':'原方法保持，仅定位','索引目录':['status'],
    'status':'preflight','freeze_sha256':sha(here/'651-免重复判定当前原生候选完整证据封存.json'),'worker_sha256':sha(here/'654-收益较弱薄壁窄缝完整区域轨迹诊断.py')}
def save():
    """客户端状态和远端实际终态分别记录。"""
    receipt.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n','utf8')
save();spec=importlib.util.spec_from_file_location('remote',here/'01-隔离内核研究远程入口.py')
remote=importlib.util.module_from_spec(spec);spec.loader.exec_module(remote);client=remote.connect()
try:
    _,out,_=client.exec_command('mkdir '+root);assert out.channel.recv_exit_status()==0
    with client.open_sftp() as sftp:
        sftp.put(str(here/'651-免重复判定当前原生候选完整证据封存.json'),root+'/freeze.json')
        sftp.put(str(here/'654-收益较弱薄壁窄缝完整区域轨迹诊断.py'),root+'/trace.py')
        record.update(status='running_actual_eight_trace_calls');save()
        _,out,_=client.exec_command('/root/miniconda3/bin/python '+root+'/trace.py');out.channel.set_combine_stderr(True)
        text=out.read().decode();(here/'657-较弱薄壁窄缝区域诊断实际控制台日志.txt').write_text(text,'utf8');print(text,flush=True)
        record['returncode']=out.channel.recv_exit_status()
        archive=here/'658-较弱薄壁窄缝八次完整轨迹归档.zip';sftp.get(root+'/weak_quality_trace_01.zip',str(archive))
        with zipfile.ZipFile(archive) as z:
            assert z.testzip() is None
            raw=json.loads(z.read('01-较弱薄壁窄缝完整区域轨迹实际记录.json'))
        record.update(status='completed_actual_eight_trace_archive_retrieved' if record['returncode']==0 else 'failed_actual_trace_archive_retrieved',
            worker_status=raw['status'],archive_sha256=sha(archive),finished_beijing=now());save();assert record['returncode']==0
finally:client.close()
