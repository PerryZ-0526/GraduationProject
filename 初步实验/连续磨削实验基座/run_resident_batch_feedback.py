"""绑定已完成批量对照的实际工作器，在授权实例执行完整原事件反馈。"""
import argparse,getpass,hashlib,json,shlex,zipfile
from datetime import datetime,timezone,timedelta
from pathlib import Path
import paramiko


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--base',type=Path,required=True)
    parser.add_argument('--profile',type=Path,required=True);parser.add_argument('--folder',type=Path,required=True)
    parser.add_argument('--mode',choices=['long','live'],default='long');parser.add_argument('--batch-size',type=int,default=5)
    parser.add_argument('--hz',type=float,default=5);args=parser.parse_args()
    endpoint=json.loads((args.base/'02-远端执行绑定.json').read_text(encoding='utf-8'))
    receipt=json.loads((args.profile/'04-完整保存回执.json').read_text(encoding='utf-8'))
    package=args.profile/'03-多工具布尔完整证据.zip';assert sha(package)==receipt['sha256']
    with zipfile.ZipFile(package) as archive:assert archive.testzip() is None
    profile=json.loads((args.profile/'02-批量布尔同父输入完整对照.json').read_text(encoding='utf-8'));assert profile['status']=='completed'
    original=json.loads((args.base/'05-常驻长序列运行绑定.json').read_text(encoding='utf-8'))
    stamp=datetime.now(timezone(timedelta(hours=8))).strftime('%Y%m%d_%H%M%S');remote='/tmp/resident_batch_'+args.mode+'_'+stamp
    args.folder.mkdir(exist_ok=False)
    client=paramiko.SSHClient();client.load_system_host_keys();password=getpass.getpass('GPU SSH password: ')
    client.connect(endpoint['host'],port=endpoint['port'],username='root',password=password,look_for_keys=False,allow_agent=False,timeout=30);del password
    try:
        sftp=client.open_sftp();sftp.mkdir(remote)
        for name in ['resident_batch_engine.py','resident_batch_boolean_service.py','resident_batch_feedback_worker.py']:sftp.put(str(Path(__file__).with_name(name)),remote+'/'+name)
        config=dict(base=endpoint['remote'],profile=receipt['remote'],sources=profile['sources'],source_cleanup_sha256=original['source_cleanup_sha256'],
            profile_report_sha256=sha(args.profile/'02-批量布尔同父输入完整对照.json'),profile_archive_sha256=receipt['sha256'])
        with sftp.file(remote+'/config.json','w') as stream:stream.write(json.dumps(config))
        python='/root/autodl-tmp/graduation_project/pamo_quality_20260927_015556_807159_retry3/venv/bin/python'
        preparation='''from pathlib import Path
import hashlib,json,shutil
root=Path(REMOTE);c=json.loads((root/'config.json').read_text());base=Path(c['base']);profile=Path(c['profile'])
def sha(p):
 with Path(p).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
assert sha(profile/'outputs/02-批量布尔同父输入完整对照.json')==c['profile_report_sha256']
assert sha(base/'resident_source_cleanup.py')==c['source_cleanup_sha256']
shutil.copytree(profile/'outputs/workers',root/'workers')
for name,digest in c['sources'].items():assert sha(root/'workers'/name)==digest
shutil.copyfile(base/'resident_source_cleanup.py',root/'workers/resident_source_cleanup.py')
shutil.copyfile(root/'resident_batch_engine.py',root/'workers/resident_batch_engine.py')
shutil.copyfile(root/'resident_batch_boolean_service.py',root/'workers/resident_batch_boolean_service.py')
shutil.copyfile(base/'manifest.json',root/'manifest.json');shutil.copytree(base/'inputs',root/'inputs')
identity=json.loads((root/'workers/build_identity.json').read_text())
for row in identity['libraries']:assert sha(row['path'])==row['sha256']
binding=dict(profile=c,workers={p.name:sha(p) for p in (root/'workers').iterdir() if p.suffix in ('.py','.cpp','.so','.json')},
 external_libraries=identity['libraries'],worker_sha256=sha(root/'resident_batch_feedback_worker.py'))
(root/'01-批量方法与依赖绑定.json').write_text(json.dumps(binding,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(remote=str(root),workers=len(binding['workers']))))
'''.replace('REMOTE',repr(remote))
        _,stdout,stderr=client.exec_command(shlex.quote(python)+' -c '+shlex.quote(preparation))
        print(stdout.read().decode(),flush=True);error=stderr.read().decode()
        if stdout.channel.recv_exit_status():raise RuntimeError(error)
        binding=dict(host=endpoint['host'],port=endpoint['port'],remote=remote,mode=args.mode,batch_size=args.batch_size,hz=args.hz,
            base_remote=endpoint['remote'],profile_remote=receipt['remote'],time_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat())
        (args.folder/'01-远端执行绑定.json').write_text(json.dumps(binding,ensure_ascii=False,indent=2),encoding='utf-8')
        env='env LD_LIBRARY_PATH=/tmp/compact_short_repair_20261006/render_trials_retry2/egl/usr/lib/x86_64-linux-gnu PYTHONPATH=/tmp/compact_short_repair_20261006/render_trials_retry2/python_deps LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libstdc++.so.6 '
        command=env+' '.join(map(shlex.quote,[python,'-u',remote+'/resident_batch_feedback_worker.py',remote,'--mode',args.mode,'--batch-size',str(args.batch_size),'--hz',str(args.hz)]))
        _,stdout,stderr=client.exec_command(command);stdout.channel.set_combine_stderr(True)
        with (args.folder/'02-实际执行日志.txt').open('x',encoding='utf-8') as log:
            for line in stdout:print(line.rstrip(),flush=True);log.write(line);log.flush()
        exit_code=stdout.channel.recv_exit_status()
        # 即使实际执行失败也保存现场，失败记录不会冒充完成或触发盲目重启。
        packing='''from pathlib import Path
import hashlib,json,zipfile
root=Path(REMOTE);target=Path(str(root)+'.zip')
with zipfile.ZipFile(target,'x',compression=zipfile.ZIP_DEFLATED) as archive:
 for p in sorted(root.rglob('*')):
  if p.is_file() and '__pycache__' not in p.parts:archive.write(p,str(p.relative_to(root)))
with target.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
print(json.dumps(dict(path=str(target),sha256=digest,bytes=target.stat().st_size)))
'''.replace('REMOTE',repr(remote))
        _,stdout,stderr=client.exec_command(shlex.quote(python)+' -c '+shlex.quote(packing));output=stdout.read().decode();error=stderr.read().decode()
        if stdout.channel.recv_exit_status():raise RuntimeError(error)
        result=json.loads(output);package=args.folder/'05-完整批量反馈与复审证据.zip';sftp.get(result['path'],str(package));assert sha(package)==result['sha256']
        with zipfile.ZipFile(package) as archive:
            assert archive.testzip() is None;result['members']=len(archive.infolist())
            for name in ['01-批量方法与依赖绑定.json','03-完整批量父反馈记录.json','04-实际保存数组完整精确复审.json']:
                if name in archive.namelist():(args.folder/name).write_bytes(archive.read(name))
        result.update(exit_code=exit_code,sha256_verified=True,crc_verified=True,remote=remote,time_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat())
        (args.folder/'06-本机完整保存回执.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(dict(local=str(args.folder),receipt=result),ensure_ascii=False),flush=True)
        if exit_code:raise RuntimeError('实际批量反馈失败，已保存完整现场')
    finally:client.close()


if __name__=='__main__':main()
