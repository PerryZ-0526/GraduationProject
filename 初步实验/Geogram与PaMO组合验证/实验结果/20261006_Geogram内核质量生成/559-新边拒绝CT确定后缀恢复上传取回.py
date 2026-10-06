"""上传冻结CT输入并执行候选实际父反馈链，保留全部结果和拒绝。"""
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
root='/tmp/geogram_native_quality_20261007_27'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
now=lambda:datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
manifest=json.loads((here/'542-新边拒绝原生CT十六刀冻结清单.json').read_text('utf8'))
receipt=here/'560-新边拒绝CT确定后缀恢复实际取回记录.json';assert not receipt.exists()
record={'生成时间':now(),'修改时间及修改内容':'首次上传全部16事件输入并运行原生反馈',
        '文档概述':'每刀原版对照用同一个候选父输入，不接旧维护输出','索引目录':['status'],
        'status':'preflight','remote':root,'worker_sha256':sha(here/'558-新边拒绝CT只恢复确定未执行末刀.py'),
        'manifest_sha256':sha(here/'542-新边拒绝原生CT十六刀冻结清单.json')}
def save():
    """客户端与工作器的状态分别绑定，下载完整归档后才写取回终态。"""
    receipt.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n','utf8')
save();client=remote.connect()
try:
    _,out,_=client.exec_command('test -d '+root+'/ct16_inputs');assert out.channel.recv_exit_status()==0
    with client.open_sftp() as sftp:
        for item in [manifest['initial']]+manifest['tools']:
            source=here/'原生CT十六刀开发冻结输入'/item['file'];assert sha(source)==item['sha256']
            sftp.put(str(source),root+'/ct16_inputs/'+item['file'])
        sftp.put(str(here/'542-新边拒绝原生CT十六刀冻结清单.json'),root+'/ct16_manifest.json')
        sftp.put(str(here/'558-新边拒绝CT只恢复确定未执行末刀.py'),root+'/ct16_feedback.py')
        record.update(status='executing_actual_native_ct16_feedback',started_beijing=now());save()
        _,out,_=client.exec_command('/root/miniconda3/bin/python '+root+'/ct16_feedback.py');out.channel.set_combine_stderr(True)
        with (here/'561-新边拒绝CT确定后缀恢复控制台日志.txt').open('x',encoding='utf8') as stream:
            for line in out:stream.write(line);stream.flush();print(line,end='',flush=True)
        record['returncode']=out.channel.recv_exit_status();save()
        archive=here/'562-新边拒绝CT确定后缀完整归档.zip';sftp.get(root+'/native_ct16_feedback_recovery_02.zip',str(archive))
        # 从完整压缩归档读取终态账本，不重复解包。
        with zipfile.ZipFile(archive) as z:
            assert z.testzip() is None
            worker=json.loads(z.read('01-原生CT十六刀反馈实际记录.json'))
        record.update(status='completed_actual_native_feedback_retrieved' if record['returncode']==0 else 'failed_actual_native_feedback_retrieved',
                      worker_status=worker['status'],archive_sha256=sha(archive),finished_beijing=now());save()
        assert record['returncode']==0
finally:client.close()
