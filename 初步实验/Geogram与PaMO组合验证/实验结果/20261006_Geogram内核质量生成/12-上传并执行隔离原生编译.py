"""核对候选源码清单后上传独立工作目录，等待同配置实际编译终态。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import importlib.util
import json

here=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('native_remote',here/'01-隔离内核研究远程入口.py')
remote=importlib.util.module_from_spec(spec)
spec.loader.exec_module(remote)
manifest=json.loads((here/'10-隔离内核候选源码准备清单.json').read_text('utf8'))
root='/tmp/geogram_native_quality_20261006_02'
record={'生成时间':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),
        '修改时间及修改内容':'首次上传原生内核改动及等待实际构建',
        '文档概述':'与原版同配置双构建；运行结束后取回实际状态及日志',
        '索引目录':['remote','status'],'status':'running','remote':root}
receipt=here/'13-隔离原生编译执行记录.json'
assert not receipt.exists()
receipt.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n','utf8')
client=remote.connect()
try:
    _,out,_=client.exec_command('mkdir '+root+' '+root+'/patch')
    assert out.channel.recv_exit_status()==0
    with client.open_sftp() as sftp:
        for name,expected in manifest['files'].items():
            source=here/'候选内核源码'/name
            assert hashlib.sha256(source.read_bytes()).hexdigest()==expected
            sftp.put(str(source),root+'/patch/'+name)
        sftp.put(str(here/'11-远端原版与候选同配置编译.py'),root+'/build.py')
        sftp.put(str(here/'03-原生布尔质量与阶段计时.cpp'),root+'/driver.cpp')
        _,out,_=client.exec_command('/root/miniconda3/bin/python '+root+'/build.py')
        out.channel.set_combine_stderr(True)
        with (here/'14-隔离原生编译控制台日志.txt').open('x',encoding='utf8') as log:
            for line in out:
                log.write(line)
                log.flush()
                print(line,end='',flush=True)
        record['returncode']=out.channel.recv_exit_status()
        sftp.get(root+'/build_record.json',str(here/'15-原版与候选真实编译记录.json'))
        compiled=json.loads((here/'15-原版与候选真实编译记录.json').read_text('utf8'))
        for stage in compiled['stages']:
            sftp.get(root+'/'+stage['name']+'.log',str(here/(stage['name']+'.log')))
        record['status']='completed_native_builds' if record['returncode']==0 else 'failed_actual_native_build'
        record['finished_beijing']=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
        receipt.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n','utf8')
        assert record['returncode']==0
finally:
    client.close()
