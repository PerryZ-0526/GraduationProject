"""使用新工作目录和已封存原生方法，输出第一次打开后不调参。"""
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
root='/tmp/geogram_native_quality_20261007_29'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
now=lambda:datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
fixed_path=here/'569-新边拒绝原生主候选完整开发终态封存清单.json'
fixed=json.loads(fixed_path.read_text('utf8'));native=fixed['method']['remote_root']
manifest_path=here/'574-新边拒绝固定方法第二批十六新参数运行前冻结清单.json'
manifest=json.loads(manifest_path.read_text('utf8'));assert manifest['method_manifest_sha256']==sha(fixed_path)
receipt=here/'577-新边拒绝固定方法第二批十六新参数评价实际取回记录.json';assert not receipt.exists()
record={'生成时间':now(),'修改时间及修改内容':'首次固定方法新参数全部计划评价',
 '文档概述':'原方法与全部输入冻结，不据结果调参；任一失败原样保留','索引目录':['status'],
 'status':'preflight','remote':root,'method_manifest_sha256':sha(fixed_path),'input_manifest_sha256':sha(manifest_path),
 'worker_sha256':sha(here/'575-新边拒绝固定方法第二批十六新参数完整交错评价.py')}
def save():
    """客户端取回状态独立于工作器语义，完整归档后才写完成。"""
    receipt.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n','utf8')
save();client=remote.connect()
try:
    _,out,_=client.exec_command('mkdir '+root+' '+root+'/inputs');assert out.channel.recv_exit_status()==0
    with client.open_sftp() as sftp:
        for i,case in enumerate(manifest['cases']):
            for role in ['parent','tool']:
                path=Path(case[role]);assert sha(path)==case[role+'_sha256']
                sftp.put(str(path),root+'/inputs/'+str(i).zfill(2)+'_'+role+'.obj')
        sftp.put(str(fixed_path),root+'/fixed_method.json')
        sftp.put(str(manifest_path),root+'/native_inputs.json')
        sftp.put(str(here/'575-新边拒绝固定方法第二批十六新参数完整交错评价.py'),root+'/benchmark.py')
        # 只读复用已验证的方法和原版，库身份由工作器在首次输出前逐项核查。
        sftp.get(native+'/build_record.json',str(here/'580-新边拒绝固定方法第二批十六新参数实际运行构建记录.json'))
        sftp.put(str(here/'580-新边拒绝固定方法第二批十六新参数实际运行构建记录.json'),root+'/build_record.json')
        for method in ['baseline','candidate']:
            sftp.symlink(native+'/'+method,root+'/'+method)
        record.update(status='executing_frozen_method_new_parameters',started_beijing=now());save()
        _,out,_=client.exec_command('/root/miniconda3/bin/python '+root+'/benchmark.py');out.channel.set_combine_stderr(True)
        with (here/'578-新边拒绝固定方法第二批十六新参数完整评价控制台日志.txt').open('x',encoding='utf8') as log:
            for line in out:log.write(line);log.flush();print(line,end='',flush=True)
        record['returncode']=out.channel.recv_exit_status();save()
        archive=here/'579-新边拒绝固定方法第二批十六新参数全部实际输出.zip'
        sftp.get(root+'/native_paired_development_01.zip',str(archive))
        # 完整ZIP先核对CRC，再直接读取终态账本，避免重复解包。
        with zipfile.ZipFile(archive) as z:
            assert z.testzip() is None
            worker=json.loads(z.read('01-固定方法十六新参数交错质量速度记录.json'))
        record.update(status='completed_fixed_method_new_parameter_archive_retrieved' if record['returncode']==0 else 'failed_fixed_method_new_parameter_archive_retrieved',
                      worker_status=worker['status'],archive_sha256=sha(archive),finished_beijing=now());save()
        assert record['returncode']==0
finally:client.close()
