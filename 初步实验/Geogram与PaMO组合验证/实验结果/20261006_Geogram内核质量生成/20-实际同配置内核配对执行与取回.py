"""验证三文件源码差异及编译终态后实际执行配对，取回全部重复与失败输出。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import importlib.util
import json
import zipfile

here=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('native_remote',here/'01-隔离内核研究远程入口.py')
remote=importlib.util.module_from_spec(spec)
spec.loader.exec_module(remote)
root='/tmp/geogram_native_quality_20261006_02'
manifest=json.loads((here/'18-原生十一同输入开发与速度运行前清单.json').read_text('utf8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
now=lambda:datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
client=remote.connect()
receipt=here/'21-原生配对执行取回记录.json'
assert not receipt.exists()
record={'生成时间':now(),'修改时间及修改内容':'首次实际执行原生十一同输入配对',
        '文档概述':'质量生成位于原生布尔内部；完整保存全部重复输出',
        '索引目录':['status','build'],'status':'preflight','remote':root,
        'input_manifest_sha256':sha(here/'18-原生十一同输入开发与速度运行前清单.json'),
        'worker_sha256':sha(here/'19-远端原生同输入交错质量速度对照.py')}


def save():
    """控制器实际进程状态与远端工作器状态分别记录。"""
    receipt.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n','utf8')


save()
try:
    with client.open_sftp() as sftp:
        for name in ['build_record.json','build_record_02.json','build_record_03.json']:
            sftp.get(root+'/'+name,str(here/name))
        build=json.loads((here/'build_record_03.json').read_text('utf8'))
        assert build['status']=='completed_two_isolated_native_builds'
        expected=json.loads((here/'10-隔离内核候选源码准备清单.json').read_text('utf8'))['files']
        before,after=build['baseline_source_hashes'],build['candidate_source_hashes']
        differences={p for p in set(before)|set(after) if before.get(p)!=after.get(p)}
        assert differences=={'src/lib/geogram/mesh/'+name for name in expected}
        assert all(after['src/lib/geogram/mesh/'+name]==digest for name,digest in expected.items())
        record['build_sha256']=sha(here/'build_record_03.json')
        record['only_three_generation_sources_differ']=sorted(differences)
        for stage in build['stages']:
            sftp.get(root+'/'+stage['name']+'.log',str(here/(stage['name']+'.log')))
        _,out,_=client.exec_command('mkdir '+root+'/inputs')
        assert out.channel.recv_exit_status()==0
        for i,case in enumerate(manifest['cases']):
            for key in ['parent','tool']:
                assert sha(case[key])==case[key+'_sha256']
                sftp.put(case[key],root+f'/inputs/{i:02d}_{key}.obj')
        sftp.put(str(here/'18-原生十一同输入开发与速度运行前清单.json'),root+'/native_inputs.json')
        sftp.put(str(here/'19-远端原生同输入交错质量速度对照.py'),root+'/benchmark.py')
        record.update(status='executing_native_paired_worker',started_worker_beijing=now()); save()
        _,out,_=client.exec_command('/root/miniconda3/bin/python '+root+'/benchmark.py')
        out.channel.set_combine_stderr(True)
        with (here/'22-原生十一同输入配对控制台日志.txt').open('x',encoding='utf8') as log:
            for line in out:
                log.write(line); log.flush(); print(line,end='',flush=True)
        record['returncode']=out.channel.recv_exit_status()
        archive=here/'23-原生配对全部重复及审计输出.zip'
        sftp.get(root+'/native_paired_development_01.zip',str(archive))
        record['archive_sha256']=sha(archive)
        output=here/'原生同输入全部重复输出'
        output.mkdir()
        with zipfile.ZipFile(archive) as z:
            # 只解包本研究输出；全部成员必须位于目标目录内。
            for name in z.namelist():
                assert (output/name).resolve().is_relative_to(output.resolve())
            z.extractall(output)
        worker=json.loads((output/'01-原生十一同输入交错质量速度记录.json').read_text('utf8'))
        record.update(status='completed_native_paired_outputs_retrieved' if record['returncode']==0 else 'failed_worker_outputs_retrieved',
                      worker_status=worker['status'],finished_beijing=now())
        save()
        assert record['returncode']==0
except BaseException as error:
    record.update(status='failed_actual_native_pair_controller',error_type=type(error).__name__,error=str(error),finished_beijing=now())
    save()
    raise
finally:
    client.close()
