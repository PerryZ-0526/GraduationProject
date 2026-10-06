"""冻结Linux完整链的接口控制、交错CPU/CUDA父反馈与逐批保存复审。"""
import argparse
from datetime import datetime,timezone,timedelta
import hashlib,json,os,subprocess,sys,zipfile
from pathlib import Path
from time import perf_counter


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    root=args.root.resolve();out=args.output.resolve();out.mkdir(exist_ok=False)
    workers=root/'workers';sha=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()
    identity=json.loads((workers/'build_identity.json').read_text());assert identity['status']=='completed'
    for row in identity['libraries']:assert sha(row['path'])==row['sha256']
    # 补传只覆盖尚未执行的工作器，全部原始归档和编译失败记录另行保留。
    with zipfile.ZipFile(root/'preflight.zip') as z:z.extractall(root)
    manifest=json.loads((root/'preflight_manifest.json').read_text())
    for row in manifest:assert sha(root/row['name'])==row['sha256']
    frozen={str(path.relative_to(root)):sha(path) for path in workers.iterdir() if path.suffix in ('.py','.cpp','.so') or path.name=='build_identity.json'}
    record=dict(time_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat(),status='running',stages=[],
        build_identity=identity,worker_sha256=frozen,preflight_members=manifest,trials=[],
        scope='同一已见CT16工具；每个预算独立合法父反馈；显示不在该计时中；CPU/CUDA交错三轮')
    def save():
        target=out/'01-Linux完整链交错批次记录.json';temporary=target.with_suffix('.tmp')
        temporary.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8');temporary.replace(target)
    def gpu():
        r=subprocess.run(['nvidia-smi','--query-compute-apps=pid,process_name,used_memory','--format=csv,noheader'],capture_output=True,text=True)
        return dict(returncode=r.returncode,stdout=r.stdout,stderr=r.stderr)
    def execute(name,argv):
        start=perf_counter();log=out/(name+'.log')
        with log.open('x') as stream:r=subprocess.run(argv,cwd=workers,stdout=stream,stderr=subprocess.STDOUT)
        record['stages'].append(dict(name=name,argv=argv,returncode=r.returncode,elapsed_ms=(perf_counter()-start)*1000,log_sha256=sha(log)))
        save();assert r.returncode==0,(name,r.returncode)
    env=dict(os.environ);env['LD_PRELOAD']='/usr/lib/x86_64-linux-gnu/libstdc++.so.6'
    os.environ.update(env);save()
    try:
        library=identity['libraries'][0]['path'];geo=root/'geogram_source'
        execute('01_compile_file_reference',['g++','-std=c++17','-O3','-DGEO_DYNAMIC_LIBS','-DGEOGRAM_USE_BUILTIN_DEPS',
            '-I'+str(geo/'src/lib'),str(workers/'geogram_file_reference.cpp'),library,
            '-Wl,-rpath,'+str(Path(library).parent),'-o',str(workers/'geogram_file_reference')])
        record['file_reference_sha256']=sha(workers/'geogram_file_reference')
        execute('02_unit_controls',[sys.executable,'-m','unittest','discover','-s',str(workers),'-p','test_*.py'])
        execute('03_geogram_interfaces',[sys.executable,str(workers/'verify_geogram_memory.py'),
            '--root',str(out/'接口控制'),'--ct-record',str(root/'inputs/ct_record.json'),'--no-simplify'])
        execute('04_exact_certificate_controls',[sys.executable,str(workers/'verify_incremental_mesh.py'),
            '--source',str(root/'diagnosis'),'--output',str(out/'02-Linux完整与增量证书三十四项对拍.json')])
        record['resource_limits']={name:Path('/sys/fs/cgroup/'+name).read_text() for name in ['cpu.max','memory.max','cpuset.cpus.effective']}
        # 各方法真实执行后立即全量复审，不同时启动另一个计时任务。
        for repeat in range(3):
            for backend in (['cpu','cuda'] if repeat%2==0 else ['cuda','cpu']):
                for name,expected in frozen.items():assert sha(root/name)==expected
                trial=dict(repeat=repeat,backend=backend,gpu_before=gpu(),status='running');record['trials'].append(trial);save()
                directory=out/f'r{repeat}_{backend}'
                execute(f'run_{repeat}_{backend}',[sys.executable,str(workers/'verified_budget_feedback.py'),
                    '--ct-record',str(root/'inputs/ct_record.json'),'--output',str(directory),
                    '--fixed-flip-certificate','--early-quality-return','--edge-backend',backend])
                trial['gpu_after']=gpu()
                execute(f'audit_{repeat}_{backend}',[sys.executable,str(workers/'audit_verified_budget_feedback.py'),'--root',str(directory)])
                trial.update(status='completed',record_sha256=sha(directory/'01-真实父反馈四预算完整记录.json'),
                    audit_sha256=sha(directory/'02-完整保存全量精确复审与四预算统计.json'))
                save();print(json.dumps(trial,ensure_ascii=False),flush=True)
        execute('05_fixed_flip_controls',[sys.executable,str(workers/'verify_fixed_flip_certificate.py'),
            '--batch',str(out/'r0_cpu'),'--output',str(out/'03-Linux固定翻边完整对拍与协议控制.json')])
        record['status']='completed';save()
    except Exception as error:
        record['status']='failed';record['error']=repr(error);save();raise


if __name__=='__main__':main()
