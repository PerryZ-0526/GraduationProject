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
root='/tmp/geogram_native_quality_20261007_27'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
receipt=here/'516-递归新边拒绝窄缝十四调用执行取回记录.json';assert not receipt.exists()
record={'生成时间':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),
 '修改时间及修改内容':'首次旋转窄缝终止现场独立取回','文档概述':'仅定位，不发布或调已评价方法',
 '索引目录':['status'],'status':'running','worker_sha256':sha(here/'514-递归新边拒绝窄缝十四调用隔离复核.py')}
client=remote.connect()
try:
    with client.open_sftp() as sftp:
        sftp.put(str(here/'514-递归新边拒绝窄缝十四调用隔离复核.py'),root+'/failure_probe.py')
        _,out,_=client.exec_command('/root/miniconda3/bin/python '+root+'/failure_probe.py');out.channel.set_combine_stderr(True)
        log=here/'517-递归新边拒绝窄缝十四调用控制台日志.txt';log.write_text(out.read().decode(),'utf8')
        record['returncode']=out.channel.recv_exit_status()
        archive=here/'518-递归新边拒绝窄缝十四调用全部输出.zip';sftp.get(root+'/gap_rejection_probe_01.zip',str(archive))
        folder=here/'递归新边拒绝窄缝十四调用全部输出';folder.mkdir()
        with zipfile.ZipFile(archive) as z:
            for name in z.namelist():assert (folder/name).resolve().is_relative_to(folder.resolve())
            z.extractall(folder)
        record.update(status='completed_rotated_gap_diagnostic_archive_retrieved',archive_sha256=sha(archive))
        worker=json.loads((folder/'01-递归新边拒绝窄缝十四调用实际记录.json').read_text('utf8'))
        print(worker['status'],worker.get('native_run'),worker.get('returned_meshes'),worker.get('valid_meshes'))
        assert record['returncode']==0
finally:
    receipt.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n','utf8');client.close()
