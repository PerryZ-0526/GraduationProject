"""上传第十七轮源码并等待实际构建，首轮编译及结果目录不修改。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import importlib.util
import json

here=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('native_remote',here/'01-隔离内核研究远程入口.py')
remote=importlib.util.module_from_spec(spec);spec.loader.exec_module(remote)
root='/tmp/geogram_native_quality_20261006_18'
expected=json.loads((here/'288-机器尺度新边受约束收缩源码清单.json').read_text('utf8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
now=lambda:datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
receipt=here/'291-机器尺度新边实际编译执行记录.json';assert not receipt.exists()
record={'生成时间':now(),'修改时间及修改内容':'首次上传第十七轮原生源码并执行构建','文档概述':'新目录，原版及首轮代码和结果不变',
        '索引目录':['status'],'status':'running','remote':root,'source_manifest_sha256':sha(here/'288-机器尺度新边受约束收缩源码清单.json')}
receipt.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n','utf8')
client=remote.connect()
try:
    _,out,_=client.exec_command('mkdir '+root+' '+root+'/patch');assert out.channel.recv_exit_status()==0
    with client.open_sftp() as sftp:
        for name,digest in expected['files'].items():
            source=here/'第十七轮机器尺度新边受约束收缩'/name;assert sha(source)==digest;sftp.put(str(source),root+'/patch/'+name)
        sftp.put(str(here/'288-机器尺度新边受约束收缩源码清单.json'),root+'/source_manifest.json')
        sftp.put(str(here/'289-机器尺度新边原生独立编译.py'),root+'/build.py')
        sftp.put(str(here/'03-原生布尔质量与阶段计时.cpp'),root+'/driver.cpp')
        _,out,_=client.exec_command('/root/miniconda3/bin/python '+root+'/build.py');out.channel.set_combine_stderr(True)
        with (here/'292-机器尺度新边实际编译控制台日志.txt').open('x',encoding='utf8') as stream:
            for line in out: stream.write(line);stream.flush();print(line,end='',flush=True)
        record['returncode']=out.channel.recv_exit_status()
        sftp.get(root+'/build_record.json',str(here/'293-机器尺度新边实际原生编译记录.json'))
        build=json.loads((here/'293-机器尺度新边实际原生编译记录.json').read_text('utf8'))
        for stage in build['stages']: sftp.get(root+'/'+stage['name']+'.log',str(here/('第十七轮_'+stage['name']+'.log')))
        record.update(status=build['status'],finished_beijing=now());receipt.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n','utf8')
        assert record['returncode']==0
except BaseException as error:
    record.update(status='failed_actual_second_build_controller',error=str(error),finished_beijing=now())
    receipt.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n','utf8');raise
finally:
    client.close()
