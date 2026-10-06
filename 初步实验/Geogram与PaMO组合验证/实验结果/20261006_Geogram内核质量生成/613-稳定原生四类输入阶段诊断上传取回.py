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
root='/tmp/geogram_native_quality_20261007_31'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
receipt=here/'614-稳定原生四类输入阶段诊断实际取回记录.json';assert not receipt.exists()
record={'生成时间':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),
 '修改时间及修改内容':'首次旋转窄缝终止现场独立取回','文档概述':'仅定位，不发布或调已评价方法',
 '索引目录':['status'],'status':'running','worker_sha256':sha(here/'612-稳定原生四类输入阶段耗时隔离诊断.py')}
client=remote.connect()
try:
    with client.open_sftp() as sftp:
        sftp.put(str(here/'612-稳定原生四类输入阶段耗时隔离诊断.py'),root+'/failure_probe.py')
        _,out,_=client.exec_command('/root/miniconda3/bin/python '+root+'/failure_probe.py');out.channel.set_combine_stderr(True)
        log=here/'615-稳定原生四类输入阶段诊断控制台日志.txt';log.write_text(out.read().decode(),'utf8')
        record['returncode']=out.channel.recv_exit_status()
        archive=here/'616-稳定原生四类输入阶段诊断完整归档.zip';sftp.get(root+'/stage_profile_01.zip',str(archive))
        # 完整压缩包直接读取，原输出不重复解包。
        with zipfile.ZipFile(archive) as z:
            assert z.testzip() is None
            worker=json.loads(z.read('01-稳定原生四类输入阶段诊断实际记录.json'))
        record.update(worker_status=worker['status'],actual_calls=len(worker['rows']))
        print(worker['status'],worker.get('native_run'),worker.get('returned_meshes'),worker.get('valid_meshes'))
        assert record['returncode']==0
finally:
    receipt.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n','utf8');client.close()
