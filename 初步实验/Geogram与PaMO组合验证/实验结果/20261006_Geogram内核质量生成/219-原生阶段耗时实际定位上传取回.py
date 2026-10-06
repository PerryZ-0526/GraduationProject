"""在已冻结生成库上执行单独阶段诊断，原正式评价记录不修改。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import importlib.util
import json
import zipfile

here=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('native_remote',here/'01-隔离内核研究远程入口.py')
remote=importlib.util.module_from_spec(spec);spec.loader.exec_module(remote)
root='/tmp/geogram_native_quality_20261006_14'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
now=lambda:datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
receipt=here/'220-原生阶段耗时实际定位执行取回记录.json';assert not receipt.exists()
record={'生成时间':now(),'修改时间及修改内容':'首次原生阶段定位上传执行',
        '文档概述':'复用原库单独诊断，不重写主评价','索引目录':['status'],'status':'running',
        'remote':root,'worker_sha256':sha(here/'218-原生阶段耗时实际定位.py')}
def save():
    """保留阶段诊断的实际控制器终态。"""
    receipt.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n','utf8')
save();client=remote.connect()
try:
    with client.open_sftp() as sftp:
        sftp.put(str(here/'218-原生阶段耗时实际定位.py'),root+'/stage_diagnosis.py')
        sftp.put(str(here/'217-原生阶段耗时诊断执行器.cpp'),root+'/stage_driver.cpp')
        _,out,_=client.exec_command('/root/miniconda3/bin/python '+root+'/stage_diagnosis.py');out.channel.set_combine_stderr(True)
        for line in out:print(line,end='',flush=True)
        record['returncode']=out.channel.recv_exit_status();save()
        archive=here/'221-原生阶段耗时实际定位全部输出.zip';sftp.get(root+'/stage_diagnosis_01.zip',str(archive))
        output=here/'原生阶段耗时实际定位输出';output.mkdir()
        with zipfile.ZipFile(archive) as z:
            for name in z.namelist():assert (output/name).resolve().is_relative_to(output.resolve())
            z.extractall(output)
        record.update(status='completed_actual_stage_diagnoses_retrieved' if record['returncode']==0 else 'failed_stage_diagnosis_retrieved',
                      archive_sha256=sha(archive),finished_beijing=now());save()
        assert record['returncode']==0
finally:client.close()
