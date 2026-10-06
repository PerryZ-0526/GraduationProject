"""独立保存诊断副本现场，不覆盖固定方法七次失败记录。"""
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
root='/tmp/geogram_native_quality_20261007_26'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
receipt=here/'502-精确插点缓存现场实际执行取回记录.json';assert not receipt.exists()
record={'生成时间':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),
 '修改时间及修改内容':'首次旋转窄缝终止现场独立取回','文档概述':'仅定位，不发布或调已评价方法',
 '索引目录':['status'],'status':'running','worker_sha256':sha(here/'500-精确插点缓存现场隔离执行.py')}
client=remote.connect()
try:
    with client.open_sftp() as sftp:
        sftp.put(str(here/'500-精确插点缓存现场隔离执行.py'),root+'/failure_probe.py')
        _,out,_=client.exec_command('/root/miniconda3/bin/python '+root+'/failure_probe.py');out.channel.set_combine_stderr(True)
        log=here/'503-精确插点缓存现场实际控制台日志.txt';log.write_text(out.read().decode(),'utf8')
        record['returncode']=out.channel.recv_exit_status()
        archive=here/'504-精确插点缓存现场全部输出.zip';sftp.get(root+'/cdt_insert_capture_01.zip',str(archive))
        folder=here/'精确插点缓存现场全部输出';folder.mkdir()
        with zipfile.ZipFile(archive) as z:
            for name in z.namelist():assert (folder/name).resolve().is_relative_to(folder.resolve())
            z.extractall(folder)
        record.update(status='completed_rotated_gap_diagnostic_archive_retrieved',archive_sha256=sha(archive))
        worker=json.loads((folder/'01-旋转窄缝隔离终止现场实际记录.json').read_text('utf8'))
        print(worker['status'],worker.get('native_run'),len(worker.get('capture_files',{})))
        assert record['returncode']==0
finally:
    receipt.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n','utf8');client.close()
