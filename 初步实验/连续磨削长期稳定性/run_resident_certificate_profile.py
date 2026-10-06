"""在授权实例私有目录执行同源认证对照，并保存源码、数组和完整证据。"""
import argparse
from datetime import datetime, timezone, timedelta
import getpass
import hashlib
import json
from pathlib import Path
import shlex
import zipfile
import paramiko


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--folder',type=Path,required=True)
    parser.add_argument('--projected-filter',action='store_true');args=parser.parse_args()
    binding=json.loads((args.folder/'02-远端执行绑定.json').read_text(encoding='utf-8'))
    stamp=datetime.now(timezone(timedelta(hours=8))).strftime('%Y%m%d_%H%M%S')
    remote='/tmp/resident_certificate_profile_'+stamp;local=args.folder/('21-源认证同源组件对照_'+stamp)
    local.mkdir(exist_ok=False)
    client=paramiko.SSHClient();client.load_system_host_keys()
    password=getpass.getpass('GPU SSH password: ')
    client.connect(binding['host'],port=binding['port'],username='root',password=password,look_for_keys=False,allow_agent=False,timeout=30)
    del password
    try:
        sftp=client.open_sftp();sftp.mkdir(remote)
        worker=Path(__file__).with_name('profile_resident_plane_certificate.py')
        sftp.put(str(worker),remote+'/'+worker.name)
        python='/root/autodl-tmp/graduation_project/pamo_quality_20260927_015556_807159_retry3/venv/bin/python'
        argv=[python,'-u',remote+'/'+worker.name,binding['remote'],remote+'/outputs']
        if args.projected_filter:argv.append('--projected-filter')
        command='LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libstdc++.so.6 '+' '.join(map(shlex.quote,argv))
        _,stdout,stderr=client.exec_command(command);stdout.channel.set_combine_stderr(True)
        with (local/'01-实际执行日志.txt').open('x',encoding='utf-8') as log:
            for line in stdout:print(line.rstrip(),flush=True);log.write(line);log.flush()
        if stdout.channel.recv_exit_status():raise RuntimeError('认证对照失败，原日志和独立目录保留')
        sftp.get(remote+'/outputs/02-精确平面排除同源组件对照.json',str(local/'02-精确平面排除同源组件对照.json'))
        # 新归档绑定实际执行源码、私有库和同源数组，旧反馈目录只读。
        code="""from pathlib import Path
import hashlib,json,zipfile
root=Path(REMOTE);target=Path(str(root)+'.zip')
with zipfile.ZipFile(target,'x',compression=zipfile.ZIP_DEFLATED) as archive:
 for path in sorted(root.rglob('*')):
  if path.is_file() and '__pycache__' not in path.parts:archive.write(path,str(path.relative_to(root)))
with target.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
print(json.dumps(dict(path=str(target),sha256=digest,bytes=target.stat().st_size)))
""".replace('REMOTE',repr(remote))
        _,stdout,stderr=client.exec_command(shlex.quote(python)+' -c '+shlex.quote(code))
        receipt=json.loads(stdout.read().decode());error=stderr.read().decode()
        if stdout.channel.recv_exit_status():raise RuntimeError(error)
        package=local/'03-源认证组件完整证据.zip';sftp.get(receipt['path'],str(package))
        with package.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
        if digest!=receipt['sha256']:raise ValueError('认证组件包摘要不一致')
        with zipfile.ZipFile(package) as archive:
            if archive.testzip() is not None:raise ValueError('认证组件包CRC不一致')
            receipt['members']=len(archive.infolist())
        receipt.update(time_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat(),remote=remote,
            source_remote=binding['remote'],sha256_verified=True,crc_verified=True)
        (local/'04-完整保存回执.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(dict(local=str(local),receipt=receipt),ensure_ascii=False),flush=True)
    finally:client.close()


if __name__=='__main__':main()
