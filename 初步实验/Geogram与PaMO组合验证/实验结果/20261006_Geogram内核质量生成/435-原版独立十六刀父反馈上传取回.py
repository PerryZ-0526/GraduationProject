"""独立保存原版连续路线，不改候选或同父对照账本。"""
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
root='/tmp/geogram_native_quality_20261006_21'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
receipt=here/'436-原版独立十六刀实际执行取回记录.json';assert not receipt.exists()
record={'生成时间':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),
 '修改时间及修改内容':'首次原版独立父反馈执行取回','文档概述':'16事件，拒绝后不接候选父',
 '索引目录':['status'],'status':'running','worker_sha256':sha(here/'434-原版独立十六刀实际父反馈执行.py')}
client=remote.connect()
try:
    with client.open_sftp() as sftp:
        sftp.put(str(here/'434-原版独立十六刀实际父反馈执行.py'),root+'/original_independent_ct16.py')
        _,out,_=client.exec_command('/root/miniconda3/bin/python '+root+'/original_independent_ct16.py');out.channel.set_combine_stderr(True)
        with (here/'437-原版独立十六刀实际控制台日志.txt').open('x',encoding='utf8') as log:
            for line in out:log.write(line);log.flush();print(line,end='',flush=True)
        record['returncode']=out.channel.recv_exit_status()
        archive=here/'438-原版独立十六刀全部实际输出.zip';sftp.get(root+'/original_ct16_independent_feedback_01.zip',str(archive))
        folder=here/'原版独立十六刀全部实际输出';folder.mkdir()
        with zipfile.ZipFile(archive) as z:
            for name in z.namelist():assert (folder/name).resolve().is_relative_to(folder.resolve())
            z.extractall(folder)
        worker=json.loads((folder/'01-原版独立十六刀实际父反馈记录.json').read_text('utf8'))
        record.update(status='completed_original_independent_feedback_retrieved',worker_status=worker['status'],archive_sha256=sha(archive))
        assert record['returncode']==0
finally:
    receipt.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n','utf8');client.close()
