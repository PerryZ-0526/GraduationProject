"""只运行已经成功构建的诊断副本，保存原始未接受对象。"""
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
root='/tmp/geogram_native_quality_20261006_12'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
now=lambda:datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
receipt=here/'180-整体拒绝对象实际捕获执行取回记录.json';assert not receipt.exists()
record={'生成时间':now(),'修改时间及修改内容':'首次执行实际诊断并完整取回',
        '文档概述':'只诊断内部整体拒绝前对象','索引目录':['status'],'status':'running',
        'remote':root,'worker_sha256':sha(here/'178-整体拒绝前共边对象实际捕获.py')}
def save():
    """控制器与远端实际返回状态分别保留。"""
    receipt.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n','utf8')
save();client=remote.connect()
try:
    with client.open_sftp() as sftp:
        sftp.put(str(here/'178-整体拒绝前共边对象实际捕获.py'),root+'/capture.py')
        sftp.put(str(here/'18-原生十一同输入开发与速度运行前清单.json'),root+'/native_inputs.json')
        _,out,_=client.exec_command('/root/miniconda3/bin/python '+root+'/capture.py');out.channel.set_combine_stderr(True)
        for line in out:print(line,end='',flush=True)
        record['returncode']=out.channel.recv_exit_status();save()
        archive=here/'181-整体拒绝前实际共边诊断输出.zip';sftp.get(root+'/proposal_capture_01.zip',str(archive))
        output=here/'整体拒绝前实际共边诊断输出';output.mkdir()
        with zipfile.ZipFile(archive) as z:
            for name in z.namelist():assert (output/name).resolve().is_relative_to(output.resolve())
            z.extractall(output)
        record.update(status='completed_actual_captures_retrieved' if record['returncode']==0 else 'failed_capture_retrieved',
                      archive_sha256=sha(archive),finished_beijing=now());save()
        assert record['returncode']==0
finally:client.close()
