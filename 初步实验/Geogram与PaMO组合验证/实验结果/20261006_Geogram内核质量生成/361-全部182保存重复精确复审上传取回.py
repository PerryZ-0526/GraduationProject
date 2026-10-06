"""取回全部重复准确检查，不修改既有原生生成账本。"""
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
receipt=here/'362-全部182重复精确复审实际取回记录.json';assert not receipt.exists()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
now=lambda:datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
record={'生成时间':now(),'修改时间及修改内容':'首次完整重复精确复审取回',
 '文档概述':'只读保存对象，不算速度重复','索引目录':['status'],'status':'running',
 'worker_sha256':sha(here/'360-十三输入全部182保存重复精确复审.py')}
client=remote.connect()
try:
    with client.open_sftp() as sftp:
        sftp.put(str(here/'360-十三输入全部182保存重复精确复审.py'),root+'/audit_all_repeats.py')
        _,out,_=client.exec_command('/root/miniconda3/bin/python '+root+'/audit_all_repeats.py');out.channel.set_combine_stderr(True)
        with (here/'363-全部182重复精确复审控制台日志.txt').open('x',encoding='utf8') as log:
            for line in out:log.write(line);log.flush();print(line,end='',flush=True)
        record['returncode']=out.channel.recv_exit_status()
        archive=here/'364-全部182保存对象精确复审全部输出.zip'
        sftp.get(root+'/all_saved_repeat_exact_audits_01.zip',str(archive))
        output=here/'十三输入全部182保存重复准确复审';output.mkdir()
        with zipfile.ZipFile(archive) as z:
            for name in z.namelist():assert (output/name).resolve().is_relative_to(output.resolve())
            z.extractall(output)
        worker=json.loads((output/'01-全部182保存对象准确复审记录.json').read_text('utf8'))
        record.update(status='completed_all_saved_repeat_exact_audits_retrieved',
            worker_status=worker['status'],totals=worker.get('totals'),archive_sha256=sha(archive),finished_beijing=now())
        assert record['returncode']==0
finally:
    receipt.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n','utf8');client.close()
