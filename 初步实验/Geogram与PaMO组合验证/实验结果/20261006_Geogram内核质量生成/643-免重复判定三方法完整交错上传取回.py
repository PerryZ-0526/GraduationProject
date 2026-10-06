"""仅上传计划和工作器，复用已认证的32份输入及三个实际原生方法。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import importlib.util
import json
import zipfile

here=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
now=lambda:datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
root='/tmp/geogram_native_quality_20261007_33'
plan={'生成时间':now(),'修改时间及修改内容':'首次三方法开发比较计划冻结','文档概述':'已见16输入全部336计划，交错一次预热六次正式，逐保存输出准确检查',
    '索引目录':['planned_calls'],'planned_calls':336,'input_manifest_sha256':sha(here/'574-新边拒绝固定方法第二批十六新参数运行前冻结清单.json'),
    'candidate_build_sha256':sha(here/'625-已保留接缝顶点免重复判定原生构建记录.json'),
    'candidate_source_manifest_sha256':sha(here/'620-已保留接缝顶点免重复判定源码清单.json'),
    'previous_build_sha256':sha(here/'513-递归前机器新边拒绝实际原生编译记录.json')}
manifest=here/'644-免重复判定十六已见三方法执行计划.json';assert not manifest.exists()
manifest.write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n','utf8')
receipt=here/'645-免重复判定三方法交错实际取回记录.json';assert not receipt.exists()
record={'生成时间':now(),'修改时间及修改内容':'首次336计划三方法实际执行取回','文档概述':'全ZIP保存，不重复解包；工作器和客户端状态单列',
    '索引目录':['status'],'status':'preflight','plan_sha256':sha(manifest),'worker_sha256':sha(here/'642-免重复判定十六已见输入三方法交错回归.py')}
def save():
    """独立保存客户端状态，不将残留running当作已取得终态。"""
    receipt.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n','utf8')
save()
spec=importlib.util.spec_from_file_location('native_remote',here/'01-隔离内核研究远程入口.py')
remote=importlib.util.module_from_spec(spec);spec.loader.exec_module(remote)
client=remote.connect()
try:
    _,out,_=client.exec_command('mkdir '+root);assert out.channel.recv_exit_status()==0
    with client.open_sftp() as sftp:
        sftp.put(str(manifest),root+'/plan.json')
        sftp.put(str(here/'642-免重复判定十六已见输入三方法交错回归.py'),root+'/benchmark.py')
        record.update(status='running_actual_336_calls',started_beijing=now());save()
        _,out,_=client.exec_command('/root/miniconda3/bin/python '+root+'/benchmark.py');out.channel.set_combine_stderr(True)
        with (here/'646-免重复判定三方法交错实际控制台日志.txt').open('x',encoding='utf8') as stream:
            for line in out:stream.write(line);stream.flush();print(line,end='',flush=True)
        record['returncode']=out.channel.recv_exit_status();save()
        archive=here/'647-免重复判定三方法完整336计划归档.zip';sftp.get(root+'/three_method_seen16_01.zip',str(archive))
        with zipfile.ZipFile(archive) as z:
            assert z.testzip() is None
            raw=json.loads(z.read('01-免重复判定十六已见三方法实际记录.json'))
        record.update(status='completed_actual_archive_retrieved' if record['returncode']==0 else 'failed_actual_archive_retrieved',
            worker_status=raw['status'],archive_sha256=sha(archive),finished_beijing=now());save()
        assert record['returncode']==0
finally:client.close()
