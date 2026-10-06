"""只运行第四刀隔离诊断，不更改原生源码和正式基准。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import importlib.util
import json
import zipfile

here=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('remote',here/'01-隔离内核研究远程入口.py')
remote=importlib.util.module_from_spec(spec);spec.loader.exec_module(remote)
root='/tmp/geogram_native_quality_20261006_20'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
receipt=here/'387-第四刀禁共面阶段诊断实际取回记录.json';assert not receipt.exists()
record={'生成时间':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),
 '修改时间及修改内容':'首次禁共面诊断执行','文档概述':'另立诊断，不混入速度',
 '索引目录':['status'],'status':'running','worker_sha256':sha(here/'385-第四刀禁共面阶段原生保存诊断.py')}
client=remote.connect()
try:
    with client.open_sftp() as sftp:
        sftp.put(str(here/'385-第四刀禁共面阶段原生保存诊断.py'),root+'/fourth_raw_diag.py')
        _,out,_=client.exec_command('/root/miniconda3/bin/python '+root+'/fourth_raw_diag.py');out.channel.set_combine_stderr(True)
        log=here/'388-第四刀禁共面阶段实际日志.txt';log.write_text(out.read().decode(),'utf8')
        record['returncode']=out.channel.recv_exit_status()
        archive=here/'389-第四刀禁共面阶段全部实际输出.zip'
        sftp.get(root+'/fourth_scene_raw_stage_diagnostic_01.zip',str(archive))
        folder=here/'第四刀禁共面原生阶段诊断';folder.mkdir()
        with zipfile.ZipFile(archive) as z:
            for name in z.namelist():assert (folder/name).resolve().is_relative_to(folder.resolve())
            z.extractall(folder)
        record.update(status='completed_native_fourth_raw_diagnosis_retrieved',archive_sha256=sha(archive))
        value=json.loads((folder/'01-第四刀禁共面原生保存实际记录.json').read_text('utf8'))
        print(json.dumps(value.get('audit'),ensure_ascii=False))
        assert record['returncode']==0
finally:
    receipt.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n','utf8');client.close()
