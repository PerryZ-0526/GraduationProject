"""验证第十六轮源码与构建绑定，执行完整配对并取回全部输出。"""
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
root='/tmp/geogram_native_quality_20261006_17'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
now=lambda:datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
receipt=here/'274-当前差面分组原生评价执行取回记录.json';assert not receipt.exists()
record={'生成时间':now(),'修改时间及修改内容':'首次第十六轮完整同输入原生评价',
        '文档概述':'生成轨迹与禁简化诊断不计入交错速度；保存全部重复',
        '索引目录':['status'],'status':'preflight','remote':root,
        'worker_sha256':sha(here/'272-当前差面分组原生交错评价与有界执行.py')}
def save():
    """控制器终态依据真实进程结果，远端账本原样保留。"""
    receipt.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n','utf8')
save();client=remote.connect()
try:
    with client.open_sftp() as sftp:
        sftp.get(root+'/build_record.json',str(here/'270-当前差面分组实际原生编译记录.json'))
        build=json.loads((here/'270-当前差面分组实际原生编译记录.json').read_text('utf8'))
        assert build['status']=='completed_candidate_build_with_verified_original_baseline_reuse'
        expected=json.loads((here/'265-当前差面触发近共面分组源码清单.json').read_text('utf8'))
        assert build['source_manifest_sha256']==sha(here/'265-当前差面触发近共面分组源码清单.json')
        for name,digest in expected['files'].items():
            assert build['candidate_source_hashes']['src/lib/geogram/mesh/'+name]==digest
        record['build_sha256']=sha(here/'270-当前差面分组实际原生编译记录.json')
        sftp.put(str(here/'18-原生十一同输入开发与速度运行前清单.json'),root+'/native_inputs.json')
        sftp.put(str(here/'272-当前差面分组原生交错评价与有界执行.py'),root+'/benchmark.py')
        record.update(status='executing_actual_third_native_pair',worker_started_beijing=now());save()
        _,out,_=client.exec_command('/root/miniconda3/bin/python '+root+'/benchmark.py');out.channel.set_combine_stderr(True)
        with (here/'275-当前差面分组原生完整评价控制台日志.txt').open('x',encoding='utf8') as log:
            for line in out: log.write(line);log.flush();print(line,end='',flush=True)
        record['returncode']=out.channel.recv_exit_status();save()
        archive=here/'276-当前差面分组原生全部重复与诊断输出.zip'
        sftp.get(root+'/native_paired_development_01.zip',str(archive));record['archive_sha256']=sha(archive)
        output=here/'第十六轮当前差面分组原生全部重复与诊断输出';output.mkdir()
        with zipfile.ZipFile(archive) as z:
            for name in z.namelist(): assert (output/name).resolve().is_relative_to(output.resolve())
            z.extractall(output)
        worker=json.loads((output/'01-原生十一同输入交错质量速度记录.json').read_text('utf8'))
        record.update(status='completed_third_native_pair_and_traces_retrieved' if record['returncode']==0 else 'failed_third_worker_retrieved',
                      worker_status=worker['status'],finished_beijing=now());save()
        assert record['returncode']==0
except BaseException as error:
    record.update(status='failed_third_actual_pair_controller',error=str(error),finished_beijing=now());save();raise
finally:
    client.close()
