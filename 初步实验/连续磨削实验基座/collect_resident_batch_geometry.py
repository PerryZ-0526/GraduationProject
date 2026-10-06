"""对已终态批量反馈追加只读几何复审，原执行证据包保持不变。"""
import argparse,getpass,hashlib,json,shlex,zipfile
from datetime import datetime,timezone,timedelta
from pathlib import Path
import paramiko


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--folder',type=Path,required=True)
    mode=parser.add_mutually_exclusive_group()
    mode.add_argument('--sequence-comparison',action='store_true');mode.add_argument('--boolean-isolation',action='store_true');args=parser.parse_args()
    binding=json.loads((args.folder/'01-远端执行绑定.json').read_text(encoding='utf-8'))
    receipt=json.loads((args.folder/'06-本机完整保存回执.json').read_text(encoding='utf-8'))
    assert sha(args.folder/'05-完整批量反馈与复审证据.zip')==receipt['sha256'] and receipt['exit_code']==0
    report=json.loads((args.folder/'03-完整批量父反馈记录.json').read_text(encoding='utf-8'))
    assert report['status'] in ('completed','completed_with_recorded_failures') and report['mode']=='long'
    client=paramiko.SSHClient();client.load_system_host_keys();password=getpass.getpass('GPU SSH password: ')
    client.connect(binding['host'],port=binding['port'],username='root',password=password,look_for_keys=False,allow_agent=False,timeout=30);del password
    try:
        remote=binding['remote'];sftp=client.open_sftp()
        # 同前缀对照另存新附件，不覆盖既有同次材料参照或原执行证据。
        worker=Path(__file__).with_name('diagnose_resident_batch_boolean.py' if args.boolean_isolation else
            'audit_resident_batch_sequence_comparison.py' if args.sequence_comparison else 'audit_resident_batch_geometry.py')
        sftp.put(str(worker),remote+'/'+worker.name)
        if args.sequence_comparison:
            prerequisite=json.loads((args.folder/'09-追加几何证据保存回执.json').read_text(encoding='utf-8'))
            assert sha(args.folder/'08-追加几何复审证据.zip')==prerequisite['sha256']
        python='/root/autodl-tmp/graduation_project/pamo_quality_20260927_015556_807159_retry3/venv/bin/python'
        env='env PYTHONPATH=/tmp/compact_short_repair_20261006/render_trials_retry2/python_deps '
        _,stdout,stderr=client.exec_command(env+' '.join(map(shlex.quote,[python,'-u',remote+'/'+worker.name,remote])))
        stdout.channel.set_combine_stderr(True)
        log_name='13-原生失败排序隔离执行日志.txt' if args.boolean_isolation else '10-同前缀对照执行日志.txt' if args.sequence_comparison else '07-追加几何复审执行日志.txt'
        with (args.folder/log_name).open('x',encoding='utf-8') as stream:
            for line in stdout:print(line.rstrip(),flush=True);stream.write(line)
        if stdout.channel.recv_exit_status():raise RuntimeError('追加几何复审失败，原执行包保留')
        names=([worker.name,'audit_resident_batch_geometry.py','10-同原扫掠前缀逐刀批量几何及质量.json',
            '03-完整批量父反馈记录.json','04-实际保存数组完整精确复审.json'] if args.sequence_comparison else
            [worker.name,'07-同次批材料参照有限几何探针.json','03-完整批量父反馈记录.json','04-实际保存数组完整精确复审.json'])
        archive_name='sequence_comparison.zip' if args.sequence_comparison else 'geometry_supplement.zip'
        if args.boolean_isolation:
            # 子进程断言日志和返回数组一并封存；本附件依赖原完整执行包中的实际父网格。
            names=[worker.name,'03-完整批量父反馈记录.json'];archive_name='boolean_failure_isolation.zip'
        code='''from pathlib import Path
import hashlib,json,zipfile
root=Path(REMOTE);target=root/ARCHIVE
names=NAMES
if BOOLEAN:names += [str(p.relative_to(root)) for p in (root/'boolean_failure_isolation').rglob('*') if p.is_file()]
with zipfile.ZipFile(target,'x',compression=zipfile.ZIP_DEFLATED) as archive:
 for name in names:archive.write(root/name,name)
with target.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
print(json.dumps(dict(path=str(target),sha256=digest,bytes=target.stat().st_size)))
'''.replace('REMOTE',repr(remote)).replace('ARCHIVE',repr(archive_name)).replace('NAMES',repr(names)).replace('BOOLEAN',repr(args.boolean_isolation))
        _,stdout,stderr=client.exec_command(shlex.quote(python)+' -c '+shlex.quote(code));text=stdout.read().decode();error=stderr.read().decode()
        if stdout.channel.recv_exit_status():raise RuntimeError(error)
        package_name='14-原生失败排序隔离证据.zip' if args.boolean_isolation else '11-同前缀对照证据.zip' if args.sequence_comparison else '08-追加几何复审证据.zip'
        result=json.loads(text);package=args.folder/package_name
        sftp.get(result['path'],str(package));assert sha(package)==result['sha256']
        with zipfile.ZipFile(package) as archive:
            assert archive.testzip() is None
            name='boolean_failure_isolation/01-原生失败排序隔离.json' if args.boolean_isolation else '10-同原扫掠前缀逐刀批量几何及质量.json' if args.sequence_comparison else '07-同次批材料参照有限几何探针.json'
            target='13-原生失败排序隔离.json' if args.boolean_isolation else name
            (args.folder/target).write_bytes(archive.read(name))
        result.update(base_archive_sha256=receipt['sha256'],time_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat(),sha256_verified=True,crc_verified=True)
        receipt_name='15-原生失败排序隔离保存回执.json' if args.boolean_isolation else '12-同前缀对照保存回执.json' if args.sequence_comparison else '09-追加几何证据保存回执.json'
        (args.folder/receipt_name).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(result,ensure_ascii=False),flush=True)
    finally:client.close()


if __name__=='__main__':main()
