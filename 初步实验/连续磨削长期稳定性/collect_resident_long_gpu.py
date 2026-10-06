"""核查已结束常驻GPU长序列，离线复审并保存完整实验资产。"""
import argparse
from datetime import datetime, timezone, timedelta
import getpass
import hashlib
import json
from pathlib import Path
import shlex
import zipfile
import uuid
import paramiko


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--folder',type=Path,required=True)
    p.add_argument('--diagnose',action='store_true');p.add_argument('--live-queue',action='store_true')
    p.add_argument('--rates-hz',nargs='+',type=float);args=p.parse_args()
    binding=json.loads((args.folder/'02-远端执行绑定.json').read_text(encoding='utf-8'));remote=binding['remote']
    client=paramiko.SSHClient();client.load_system_host_keys()
    password=getpass.getpass('GPU SSH password: ')
    client.connect(binding['host'],port=binding['port'],username='root',password=password,look_for_keys=False,allow_agent=False,timeout=30)
    del password
    python='/root/autodl-tmp/graduation_project/pamo_quality_20260927_015556_807159_retry3/venv/bin/python'
    try:
        sftp=client.open_sftp()
        if args.live_queue:
            worker=Path(__file__).resolve().parents[1]/'连续磨削实验基座/resident_live_queue_worker.py'
            sftp.put(str(worker),remote+'/resident_live_queue_worker.py')
            runtime='/tmp/compact_short_repair_20261006/render_trials_retry2'
            command='env PYTHONPATH='+runtime+'/python_deps LD_LIBRARY_PATH='+runtime+'/egl/usr/lib/x86_64-linux-gnu LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libstdc++.so.6 VTK_DEFAULT_OPENGL_WINDOW=vtkEGLRenderWindow '+shlex.quote(python)+' -u '+shlex.quote(remote+'/resident_live_queue_worker.py')+' '+shlex.quote(remote)
            # 完整轨迹分母保持，只显式选择本批实际输入频率；历史三档默认值保持。
            if args.rates_hz:command+=' --rates-hz '+' '.join(shlex.quote(str(hz)) for hz in args.rates_hz)
            _,stdout,stderr=client.exec_command(command);stdout.channel.set_combine_stderr(True)
            with (args.folder/'13-真实输入队列与GPU像素.log').open('x',encoding='utf-8') as log:
                for line in stdout:print(line.rstrip(),flush=True);log.write(line);log.flush()
            if stdout.channel.recv_exit_status():raise RuntimeError('真实输入队列实验异常，现场保留')
            sftp.get(remote+'/live_queue/01-真实输入队列与GPU像素完整记录.json',str(args.folder/'14-真实输入队列与GPU像素完整记录.json'))
            code="""from pathlib import Path
import hashlib,json,zipfile
root=Path(REMOTE);target=Path(str(root)+'_live_queue_complete.zip')
with zipfile.ZipFile(target,'x',compression=zipfile.ZIP_DEFLATED) as archive:
 archive.write(root/'resident_live_queue_worker.py','resident_live_queue_worker.py')
 for path in sorted((root/'live_queue').rglob('*')):
  if path.is_file():archive.write(path,str(path.relative_to(root)))
with target.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
print(json.dumps({'path':str(target),'sha256':digest,'bytes':target.stat().st_size}))
""".replace('REMOTE',repr(remote))
            _,stdout,stderr=client.exec_command(shlex.quote(python)+' -c '+shlex.quote(code))
            receipt=json.loads(stdout.read().decode('utf-8'));error=stderr.read().decode('utf-8')
            if stdout.channel.recv_exit_status():raise RuntimeError(error)
            target=args.folder/'15-真实输入队列与GPU像素完整证据.zip';sftp.get(receipt['path'],str(target))
            with target.open('rb') as stream:actual=hashlib.file_digest(stream,'sha256').hexdigest()
            if actual!=receipt['sha256']:raise ValueError('真实像素归档摘要不一致')
            with zipfile.ZipFile(target) as archive:
                if archive.testzip() is not None:raise ValueError('真实像素归档CRC不一致')
                receipt['members']=len(archive.infolist())
            receipt.update(local=str(target),sha256_verified=True,crc_verified=True,
                prerequisite=json.loads((args.folder/'12-完整资产本机保存回执.json').read_text(encoding='utf-8'))['sha256'])
            (args.folder/'16-真实队列与像素本机保存回执.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
            print(json.dumps(receipt,ensure_ascii=False),flush=True)
            return
        if args.diagnose:
            code="""from pathlib import Path
import json
from collections import Counter
root=Path(REMOTE)
report=json.loads((root/'02-常驻长序列完整记录.json').read_text())
for run in report['runs']:
 ledger=json.loads((Path(run['output'])/'01-真实父反馈四预算完整记录.json').read_text())
 failed=[e for e in ledger['routes'][0]['events'] if e['status']=='source_rejected']
 for e in failed:
  repair=e.get('repair') or {};cluster=repair.get('source_cluster_fallback') or {}
  print(json.dumps({'route':run['route'],'reference':run['reference'],'step':e['step']+1,'error':e.get('error'),'boolean':e.get('boolean'),
   'source_check':e.get('source_check'),'repair_operations':len(repair.get('operations',[])),
   'candidate_edges':repair.get('candidate_edges'),'repair_elapsed_ms':repair.get('total_elapsed_ms'),
   'repair_overrun':repair.get('budget_overrun'),'cut_and_maintenance_ms':e.get('cut_and_maintenance_ms'),
   'cluster_fallback':dict(candidate=cluster.get('candidate'),accepted=cluster.get('accepted'),reason=cluster.get('reason'),
    operations=len(cluster.get('operations',[])),rejection_reasons=dict(Counter(r['reason'] for r in cluster.get('rejections',[]))),
    component_euler_before=cluster.get('component_euler_before'),component_euler_after=cluster.get('component_euler_after'),
    candidate_check=cluster.get('candidate_check'),original_failed_check=cluster.get('original_failed_check'))},ensure_ascii=False))
""".replace('REMOTE',repr(remote))
            _,stdout,stderr=client.exec_command(shlex.quote(python)+' -c '+shlex.quote(code))
            raw=stdout.read().decode('utf-8');error=stderr.read().decode('utf-8')
            print(raw,flush=True);print(error,flush=True)
            if stdout.channel.recv_exit_status():raise RuntimeError('失败记录读取异常')
            # 将小型真实终态摘要单独保存，避免诊断只留在可能截断的控制台里。
            rows=[json.loads(line) for line in raw.splitlines() if line.strip()]
            receipt=dict(time_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat(),
                source_remote=remote,execution_record_sha256=hashlib.sha256((args.folder/'06-常驻长序列完整记录.json').read_bytes()).hexdigest(),records=rows)
            with (args.folder/'20-实际终态拒绝阶段摘要.json').open('x',encoding='utf-8') as stream:
                json.dump(receipt,stream,ensure_ascii=False,indent=2)
            return
        auditor=Path(__file__).with_name('audit_resident_long_arrays.py')
        audit_name='audit_resident_long_arrays_'+uuid.uuid4().hex[:8]+'.py'
        sftp.put(str(auditor),remote+'/'+audit_name)
        # 使用另一任务已保存的私有VTK运行依赖，不安装或改动共享Python环境。
        command='env PYTHONPATH=/tmp/compact_short_repair_20261006/render_trials_retry2/python_deps LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libstdc++.so.6 '+shlex.quote(python)+' -u '+shlex.quote(remote+'/'+audit_name)+' '+shlex.quote(remote)
        _,stdout,stderr=client.exec_command(command);stdout.channel.set_combine_stderr(True)
        with (args.folder/('08-离线完整复审-'+audit_name[-11:-3]+'.log')).open('x',encoding='utf-8') as log:
            for line in stdout:print(line.rstrip(),flush=True);log.write(line);log.flush()
        if stdout.channel.recv_exit_status():raise RuntimeError('离线完整复审失败，现场保留')
        for name,local in [('04-保存对象完整精确复审.json','09-保存对象完整精确复审.json'),('05-独立材料参照逐帧有限探针.json','10-独立材料参照逐帧有限探针.json')]:
            sftp.get(remote+'/'+name,str(args.folder/local))
        code="""from pathlib import Path
import hashlib,json,zipfile
root=Path(REMOTE);target=Path(str(root)+'_complete.zip')
with zipfile.ZipFile(target,'x',compression=zipfile.ZIP_DEFLATED) as archive:
 for path in sorted(root.rglob('*')):
  if path.is_file() and '__pycache__' not in path.parts:archive.write(path,str(path.relative_to(root)))
with target.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
print(json.dumps({'path':str(target),'sha256':digest,'bytes':target.stat().st_size}))
""".replace('REMOTE',repr(remote))
        _,stdout,stderr=client.exec_command(shlex.quote(python)+' -c '+shlex.quote(code))
        receipt=json.loads(stdout.read().decode('utf-8'));error=stderr.read().decode('utf-8')
        if stdout.channel.recv_exit_status():raise RuntimeError(error)
        package=args.folder/'11-常驻长轨迹完整执行与复审证据.zip';sftp.get(receipt['path'],str(package))
        with package.open('rb') as stream:actual=hashlib.file_digest(stream,'sha256').hexdigest()
        if actual!=receipt['sha256']:raise ValueError('完整归档摘要不一致')
        with zipfile.ZipFile(package) as archive:
            if archive.testzip() is not None:raise ValueError('完整归档CRC不一致')
            receipt['members']=len(archive.infolist())
        receipt.update(local=str(package),sha256_verified=True,crc_verified=True)
        (args.folder/'12-完整资产本机保存回执.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(receipt,ensure_ascii=False),flush=True)
        sftp.close()
    finally:client.close()


if __name__=='__main__':main()
