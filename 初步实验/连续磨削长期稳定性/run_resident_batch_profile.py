"""在授权GPU实例私有目录运行批量布尔，保留全部实际源码、原工具和失败。"""
import argparse
from datetime import datetime,timezone,timedelta
import getpass,hashlib,json,shlex,zipfile
from pathlib import Path
import paramiko


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--folder',type=Path,required=True);args=p.parse_args()
    binding=json.loads((args.folder/'02-远端执行绑定.json').read_text(encoding='utf-8'))
    stamp=datetime.now(timezone(timedelta(hours=8))).strftime('%Y%m%d_%H%M%S')
    remote='/tmp/resident_batch_profile_'+stamp;local=args.folder/('22-多工具布尔同父对照_'+stamp);local.mkdir(exist_ok=False)
    client=paramiko.SSHClient();client.load_system_host_keys();password=getpass.getpass('GPU SSH password: ')
    client.connect(binding['host'],port=binding['port'],username='root',password=password,look_for_keys=False,allow_agent=False,timeout=30);del password
    try:
        sftp=client.open_sftp();sftp.mkdir(remote);worker=Path(__file__).with_name('profile_resident_batch_boolean.py')
        files=[worker]+[Path(__file__).resolve().parents[1]/'连续磨削实验基座'/name for name in ['geogram_batch_memory.cpp','geogram_batch_memory.py']]
        for path in files:sftp.put(str(path),remote+'/'+path.name)
        python='/root/autodl-tmp/graduation_project/pamo_quality_20260927_015556_807159_retry3/venv/bin/python'
        command='env PYTHONPATH=/tmp/compact_short_repair_20261006/render_trials_retry2/python_deps LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libstdc++.so.6 '+' '.join(map(shlex.quote,[python,'-u',remote+'/'+worker.name,binding['remote'],remote+'/outputs']))
        _,stdout,stderr=client.exec_command(command);stdout.channel.set_combine_stderr(True)
        with (local/'01-实际执行日志.txt').open('x',encoding='utf-8') as log:
            for line in stdout:print(line.rstrip(),flush=True);log.write(line);log.flush()
        if stdout.channel.recv_exit_status():raise RuntimeError('批量布尔对照失败，原目录和日志保留')
        sftp.get(remote+'/outputs/02-批量布尔同父输入完整对照.json',str(local/'02-批量布尔同父输入完整对照.json'))
        code="""from pathlib import Path
import hashlib,json,zipfile
root=Path(REMOTE);target=Path(str(root)+'.zip')
with zipfile.ZipFile(target,'x',compression=zipfile.ZIP_DEFLATED) as archive:
 for path in sorted(root.rglob('*')):
  if path.is_file() and '__pycache__' not in path.parts:archive.write(path,str(path.relative_to(root)))
with target.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
print(json.dumps(dict(path=str(target),sha256=digest,bytes=target.stat().st_size)))
""".replace('REMOTE',repr(remote))
        _,stdout,stderr=client.exec_command(shlex.quote(python)+' -c '+shlex.quote(code));receipt=json.loads(stdout.read().decode());error=stderr.read().decode()
        if stdout.channel.recv_exit_status():raise RuntimeError(error)
        package=local/'03-多工具布尔完整证据.zip';sftp.get(receipt['path'],str(package))
        with package.open('rb') as stream:assert hashlib.file_digest(stream,'sha256').hexdigest()==receipt['sha256']
        with zipfile.ZipFile(package) as archive:
            assert archive.testzip() is None;receipt['members']=len(archive.infolist())
        receipt.update(time_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat(),remote=remote,source_remote=binding['remote'],sha256_verified=True,crc_verified=True)
        (local/'04-完整保存回执.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(dict(local=str(local),receipt=receipt),ensure_ascii=False),flush=True)
    finally:client.close()


if __name__=='__main__':main()
