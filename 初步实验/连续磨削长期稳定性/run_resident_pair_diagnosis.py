"""在授权GPU实例的私有目录诊断保存源，下载完整逐阶段证据。"""
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
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--folder',type=Path,required=True)
    parser.add_argument('--repair-limits',action='store_true')
    parser.add_argument('--cluster-repair',action='store_true')
    parser.add_argument('--cluster-scale-trials',action='store_true')
    parser.add_argument('--active-anchor-trials',action='store_true')
    args=parser.parse_args();binding=json.loads((args.folder/'02-远端执行绑定.json').read_text(encoding='utf-8'))
    stamp=datetime.now(timezone(timedelta(hours=8))).strftime('%Y%m%d_%H%M%S')
    remote='/tmp/resident_pair_diagnosis_'+stamp;local=args.folder/('19-逐阶段源相交归因_'+stamp)
    local.mkdir(exist_ok=False);client=paramiko.SSHClient();client.load_system_host_keys()
    password=getpass.getpass('GPU SSH password: ')
    client.connect(binding['host'],port=binding['port'],username='root',password=password,look_for_keys=False,allow_agent=False,timeout=30)
    del password
    try:
        sftp=client.open_sftp();sftp.mkdir(remote)
        worker=Path(__file__).with_name('diagnose_resident_source_pairs.py')
        checker=Path(__file__).resolve().parents[1]/'实时预算局部质量优化/exact_mesh_pairs.cpp'
        for path in (worker,checker):sftp.put(str(path),remote+'/'+path.name)
        if args.cluster_repair:
            # 候选源码使用独立文件名，旧运行目录及已冻结清理源码保持。
            helper=Path(__file__).resolve().parents[1]/'连续磨削实验基座/resident_source_cleanup.py'
            sftp.put(str(helper),remote+'/resident_source_cleanup_candidate.py')
        python='/root/autodl-tmp/graduation_project/pamo_quality_20260927_015556_807159_retry3/venv/bin/python'
        # 可选隔离对照只放大修复时间，不把诊断结果加入原父反馈。
        argv=[python,'-u',remote+'/'+worker.name,binding['remote'],remote+'/outputs']
        if args.repair_limits:argv.append('--repair-limits')
        if args.cluster_repair:argv.append('--cluster-repair')
        if args.cluster_scale_trials:argv.append('--cluster-scale-trials')
        if args.active_anchor_trials:argv.append('--active-anchor-trials')
        command=' '.join(map(shlex.quote,argv))
        _,stdout,stderr=client.exec_command(command);stdout.channel.set_combine_stderr(True)
        with (local/'01-实际执行日志.txt').open('x',encoding='utf-8') as log:
            for line in stdout:print(line.rstrip(),flush=True);log.write(line);log.flush()
        if stdout.channel.recv_exit_status():raise RuntimeError('源面定位失败，原目录保留')
        sftp.get(remote+'/outputs/02-逐阶段精确相交面归因.json',str(local/'02-逐阶段精确相交面归因.json'))
        code="""from pathlib import Path
import hashlib,json,zipfile
root=Path(REMOTE);target=Path(str(root)+'.zip')
with zipfile.ZipFile(target,'x',compression=zipfile.ZIP_DEFLATED) as archive:
 for path in sorted(root.rglob('*')):
  if path.is_file():archive.write(path,str(path.relative_to(root)))
with target.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
print(json.dumps(dict(path=str(target),sha256=digest,bytes=target.stat().st_size)))
""".replace('REMOTE',repr(remote))
        _,stdout,stderr=client.exec_command(shlex.quote(python)+' -c '+shlex.quote(code))
        receipt=json.loads(stdout.read().decode());error=stderr.read().decode()
        if stdout.channel.recv_exit_status():raise RuntimeError(error)
        package=local/'03-完整逐阶段归因证据.zip';sftp.get(receipt['path'],str(package))
        with package.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
        if digest!=receipt['sha256']:raise ValueError('归因包摘要不一致')
        with zipfile.ZipFile(package) as archive:
            if archive.testzip() is not None:raise ValueError('归因包CRC不一致')
            receipt['members']=len(archive.infolist())
        receipt.update(time_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat(),remote=remote,
            source_remote=binding['remote'],sha256_verified=True,crc_verified=True)
        (local/'04-完整保存回执.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(dict(local=str(local),receipt=receipt),ensure_ascii=False),flush=True)
    finally:client.close()


if __name__=='__main__':main()
