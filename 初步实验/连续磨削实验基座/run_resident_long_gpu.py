"""在授权GPU上冻结常驻质量工作器，并从初态运行完整长轨迹。"""
import argparse
import getpass
import hashlib
import json
from pathlib import Path
import shlex
import zipfile
import paramiko


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--prepared', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--inspect', action='store_true')
    p.add_argument('--complete-short-repair', action='store_true')
    p.add_argument('--geogram-simplify', action='store_true')
    p.add_argument('--cancel-opposed-after-repair', action='store_true')
    p.add_argument('--cluster-source-fallback', action='store_true')
    p.add_argument('--cluster-tolerance-mm', type=float, default=1e-10)
    p.add_argument('--certificate-profile', type=Path)
    args = p.parse_args()
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    password = getpass.getpass('GPU SSH password: ')
    client.connect('connect.westb.seetacloud.com', port=14137, username='root', password=password,
                   look_for_keys=False, allow_agent=False, timeout=30)
    del password
    try:
        if args.inspect:
            code = """from pathlib import Path
import json
root=Path('/tmp/filtered_source_certificate_20261006')
print(json.dumps({'workers':str(root/'workers'),'status':json.loads((root/'01-过滤精确谓词完整GPU反馈执行记录.json').read_text())['status']},ensure_ascii=False))
for name in ['geogram_memory.py','verified_budget_feedback.py']:
 print('SOURCE',name);print((root/'workers'/name).read_text())
"""
            command = '/root/autodl-tmp/graduation_project/pamo_quality_20260927_015556_807159_retry3/venv/bin/python -c ' + shlex.quote(code)
            _, stdout, stderr = client.exec_command(command)
            print(stdout.read().decode('utf-8'), flush=True)
            print(stderr.read().decode('utf-8'), flush=True)
            if stdout.channel.recv_exit_status():
                raise RuntimeError('冻结工作器只读核查失败')
            return
        args.output.mkdir(parents=True, exist_ok=False)
        prepared = args.prepared.resolve()
        manifest = json.loads((prepared / '01-完整范围冻结清单.json').read_text(encoding='utf-8'))
        override = None
        if args.certificate_profile:
            # 只允许接入已完整同源对照并保存核对的原生库，候选源码和实际库逐件绑定。
            profile = args.certificate_profile
            record_path = profile / '02-精确平面排除同源组件对照.json'
            record = json.loads(record_path.read_text(encoding='utf-8'))
            saved = json.loads((profile / '04-完整保存回执.json').read_text(encoding='utf-8'))
            assert record['status'] == 'completed' and record['filter_kind'] == 'exact_projected_separation'
            archive_path = profile / '03-源认证组件完整证据.zip'
            assert hashlib.sha256(archive_path.read_bytes()).hexdigest() == saved['sha256']
            with zipfile.ZipFile(archive_path) as archive:
                assert archive.testzip() is None
                files = {name:hashlib.sha256(archive.read('outputs/candidate/'+name)).hexdigest()
                         for name in ['incremental_mesh_memory.cpp','incremental_mesh_memory.py','libincremental_mesh_memory.so','exact_mesh_memory.cpp']}
            override = dict(remote=saved['remote'],files=files,profile_report_sha256=hashlib.sha256(record_path.read_bytes()).hexdigest(),
                frozen_source_sha256=record['frozen_source_sha256'],method=record['filter_kind'])
        remote = '/tmp/resident_long_feedback_' + args.output.name.split('_')[-1]
        package = args.output / '01-输入与常驻入口.zip'
        names = {r['initial_mesh']: r['initial_mesh_sha256'] for r in manifest['routes']}
        for route in manifest['routes']:
            names.update({t['mesh']: t['sha256'] for t in route['prefix_tools']})
        # 输入包含原来的扫掠工具，逐件核对摘要，不能只保留最后一个钻头位置。
        with zipfile.ZipFile(package, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
            # 必要修复和认证优化显式绑定为新方法版本，旧批次配置及父链不改写。
            archive.writestr('run_config.json', json.dumps({'complete_short_repair':args.complete_short_repair,'geogram_simplify':args.geogram_simplify,'cancel_opposed_after_repair':args.cancel_opposed_after_repair,'cluster_source_fallback':args.cluster_source_fallback,'cluster_tolerance_mm':args.cluster_tolerance_mm,'source_certificate_override':override}))
            archive.write(prepared / '01-完整范围冻结清单.json', 'manifest.json')
            for name, expected in names.items():
                path = prepared / 'inputs' / name
                if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                    raise ValueError('冻结输入摘要不一致：' + name)
                archive.write(path, 'inputs/' + name)
            archive.write(Path(__file__).with_name('resident_long_worker.py'), 'resident_long_worker.py')
            archive.write(Path(__file__).with_name('resident_source_cleanup.py'), 'resident_source_cleanup.py')
        sftp = client.open_sftp()
        sftp.put(str(package), remote + '.zip')
        bootstrap = """from pathlib import Path
import hashlib,json,shutil,subprocess,sys,zipfile
root=Path(REMOTE)
root.mkdir(exist_ok=False)
with zipfile.ZipFile(str(root)+'.zip') as archive:archive.extractall(root)
shutil.copytree('/tmp/filtered_source_certificate_20261006/workers',root/'workers')
override=json.loads((root/'run_config.json').read_text()).get('source_certificate_override')
if override:
 profile=Path(override['remote'])/'outputs';sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
 assert sha(profile/'02-精确平面排除同源组件对照.json')==override['profile_report_sha256']
 assert sha(root/'workers/incremental_mesh_memory.cpp')==override['frozen_source_sha256']
 for name,expected in override['files'].items():
  assert sha(profile/'candidate'/name)==expected
  shutil.copyfile(profile/'candidate'/name,root/'workers'/name)
 identity_path=root/'workers/build_identity.json';identity=json.loads(identity_path.read_text())
 identity['source_certificate_override']=override
 for row in identity['libraries']:
  if Path(row['path']).name=='libincremental_mesh_memory.so':
   row.update(path=str(root/'workers/libincremental_mesh_memory.so'),sha256=sha(root/'workers/libincremental_mesh_memory.so'))
 identity_path.write_text(json.dumps(identity,ensure_ascii=False,indent=2))
 shutil.copytree(profile/'reference',root/'reference_workers')
 # 启动前复用原五尺度近接触实验，接触和穿入负例不允许因排除优化放行。
 with (root/'04-近接触核对实际日志.txt').open('x') as log:
  result=subprocess.run([sys.executable,str(root/'workers/verify_filtered_mesh_controls.py'),'--root',str(root)],stdout=log,stderr=subprocess.STDOUT)
 assert result.returncode==0,'近接触源认证核对失败，未启动完整长轨迹'
""".replace('REMOTE', repr(remote))
        python = '/root/autodl-tmp/graduation_project/pamo_quality_20260927_015556_807159_retry3/venv/bin/python'
        _, stdout, stderr = client.exec_command('env LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libstdc++.so.6 ' + shlex.quote(python) + ' -c ' + shlex.quote(bootstrap))
        error = stderr.read().decode('utf-8');stdout.read()
        if stdout.channel.recv_exit_status():
            raise RuntimeError(error)
        receipt = dict(host='connect.westb.seetacloud.com', port=14137, remote=remote,
                       input_package_sha256=hashlib.sha256(package.read_bytes()).hexdigest())
        (args.output / '02-远端执行绑定.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
        command = 'env LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libstdc++.so.6 ' + shlex.quote(python) + ' -u ' + shlex.quote(remote + '/resident_long_worker.py')
        _, stdout, stderr = client.exec_command(command)
        # 合并错误流并持续消费，避免大量原生诊断填满SSH通道。
        stdout.channel.set_combine_stderr(True)
        # 实际进度逐行写出，观察等待不会触发重启或修改原批次。
        with (args.output / '03-远端运行.log').open('x', encoding='utf-8') as log:
            for line in stdout:
                print(line.rstrip(), flush=True);log.write(line);log.flush()
        error = stderr.read().decode('utf-8')
        if error:
            with (args.output / '04-远端错误.log').open('x', encoding='utf-8') as log:log.write(error)
            print(error[-3000:], flush=True)
        code = stdout.channel.recv_exit_status()
        for name in ['01-常驻长序列运行绑定.json', '02-常驻长序列完整记录.json', '03-在线阶段统计与输入积压.json']:
            if any(item.filename == name for item in sftp.listdir_attr(remote)):
                sftp.get(remote + '/' + name, str(args.output / name.replace('01-', '05-').replace('02-', '06-').replace('03-', '07-')))
        print(json.dumps({'returncode': code, 'remote': remote}, ensure_ascii=False), flush=True)
        sftp.close()
        if code:
            raise RuntimeError('远端实验退出：' + str(code))
    finally:
        client.close()


if __name__ == '__main__':
    main()
