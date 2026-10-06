"""独立编译缓存源证书，完成协议对拍后运行完整GPU预算反馈和真实像素交付。"""
import argparse
from datetime import datetime,timezone,timedelta
import hashlib,json,os
from pathlib import Path
import shutil,subprocess,sys,zipfile


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--baseline',type=Path,required=True)
    p.add_argument('--root',type=Path,required=True);p.add_argument('--incoming',type=Path,required=True);args=p.parse_args()
    base,root=args.baseline.resolve(),args.root.resolve();assert base.parent==root.parent and base!=root
    assert json.loads((base/'03-三轮四预算与真实GPU像素终态汇总.json').read_text())['status']=='completed'
    root.mkdir(exist_ok=False);sha=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()
    for name in ['reference_workers','workers']:shutil.copytree(base/'workers',root/name)
    with zipfile.ZipFile(args.incoming) as z:z.extractall(root/'incoming')
    workers=root/'workers';shutil.copyfile(root/'incoming/incremental_mesh_memory_cached.cpp',workers/'incremental_mesh_memory.cpp')
    shutil.copyfile(root/'incoming/verify_cached_source_certificate.py',workers/'verify_cached_source_certificate.py')
    record=dict(time_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat(),status='running',baseline=str(base),
        incoming_sha256=sha(args.incoming),stages=[],trials=[],renders=[],gpu_shared=True,
        scope='复用同几何父缓存，不减少变化面全域精确核查；新旧预算路线各自反馈，全部分母及失败保持')
    target=root/'01-缓存源认证完整GPU反馈执行记录.json'
    def save():
        temp=target.with_suffix('.tmp');temp.write_text(json.dumps(record,ensure_ascii=False,indent=2));temp.replace(target)
    environment=dict(os.environ,LD_PRELOAD='/usr/lib/x86_64-linux-gnu/libstdc++.so.6')
    def execute(name,argv,cwd=workers,env=environment):
        log=root/(name+'.log')
        with log.open('x') as stream:r=subprocess.run(argv,cwd=cwd,env=env,stdout=stream,stderr=subprocess.STDOUT)
        record['stages'].append(dict(name=name,argv=argv,returncode=r.returncode,log_sha256=sha(log)));save()
        assert r.returncode==0,(name,r.returncode)
    def gpu():
        r=subprocess.run(['nvidia-smi','--query-compute-apps=pid,process_name,used_memory','--format=csv,noheader'],capture_output=True,text=True)
        return dict(returncode=r.returncode,stdout=r.stdout,stderr=r.stderr)
    save()
    try:
        execute('compile_cached_certificate',['g++','-std=c++17','-O3','-DNDEBUG','-DCGAL_DISABLE_GMP','-shared','-fPIC',
            '-fno-fast-math','-ffp-contract=off','-frounding-math',str(workers/'incremental_mesh_memory.cpp'),
            '-o',str(workers/'libincremental_mesh_memory.so')])
        for name in ['reference_workers','workers']:
            identity=json.loads((root/name/'build_identity.json').read_text())
            for row in identity['libraries']:
                path=Path(row['path']);assert sha(path)==row['sha256']
                if path.parent==base/'workers':
                    row['path']=str(root/name/path.name);row['sha256']=sha(root/name/path.name)
            identity['copied_from_identity_sha256']=sha(base/'workers/build_identity.json')
            identity['variant']='cached_parent_geometry' if name=='workers' else 'frozen_reference'
            if name=='workers':identity['variant_compile_log_sha256']=sha(root/'compile_cached_certificate.log')
            (root/name/'build_identity.json').write_text(json.dumps(identity,ensure_ascii=False,indent=2))
        record['frozen_sources_and_libraries']={str(p.relative_to(root)):sha(p) for name in ['reference_workers','workers']
            for p in (root/name).iterdir() if p.suffix in ['.py','.cpp','.so','.json']};save()
        baseline_record=json.loads((base/'r0_workers/01-真实父反馈四预算完整记录.json').read_text())
        initial='/tmp/geogram_certified_pairs_20261006_r3/inputs/initial.obj'
        assert sha(initial)==baseline_record['initial_sha256']
        execute('same_parent_96_pairs',[sys.executable,str(workers/'verify_cached_source_certificate.py'),
            '--root',str(root),'--batch',str(base/'r0_workers'),'--initial',initial])
        execute('existing_34_certificate_controls',[sys.executable,str(workers/'verify_incremental_mesh.py'),
            '--source','/tmp/geogram_budget_full_20261006/diagnosis','--output',str(root/'03-缓存证书完整正负控制.json')])
        execute('existing_fixed_flip_controls',[sys.executable,str(workers/'verify_fixed_flip_certificate.py'),
            '--batch',str(base/'r0_workers'),'--output',str(root/'04-缓存固定翻边协议及全量核对.json')])
        ct='/tmp/geogram_certified_pairs_20261006_r3/inputs/ct_record.json'
        for repeat in range(3):
            for name in (['reference_workers','workers'] if repeat%2==0 else ['workers','reference_workers']):
                for path,expected in record['frozen_sources_and_libraries'].items():assert sha(root/path)==expected
                current=root/name;out=root/f'r{repeat}_{name}';trial=dict(repeat=repeat,variant=name,status='running',gpu_before=gpu())
                record['trials'].append(trial);save()
                execute(f'run_{repeat}_{name}',[sys.executable,str(current/'verified_budget_feedback.py'),'--ct-record',ct,
                    '--output',str(out),'--fixed-flip-certificate','--early-quality-return','--edge-backend','cuda','--certified-operand-pairs'],current)
                execute(f'audit_{repeat}_{name}',[sys.executable,str(current/'audit_verified_budget_feedback.py'),'--root',str(out)],current)
                trial.update(status='completed',gpu_after=gpu(),record_sha256=sha(out/'01-真实父反馈四预算完整记录.json'),
                    audit_sha256=sha(out/'02-完整保存全量精确复审与四预算统计.json'));save()
        # 复用已经完整冻结的私有渲染轮子和EGL，不重复下载或修改共享环境。
        rendering=base/'render_trials_retry2';render_env=dict(environment,PYTHONPATH=str(rendering/'python_deps'),
            LD_LIBRARY_PATH=str(rendering/'egl/usr/lib/x86_64-linux-gnu')+':'+environment.get('LD_LIBRARY_PATH',''),
            VTK_DEFAULT_OPENGL_WINDOW='vtkEGLRenderWindow')
        record['render_runtime_record_sha256']=sha(rendering/'01-私有GPU渲染依赖与完整反馈执行记录.json');save()
        for name,budget in [('reference_workers',100),('workers',100),('workers',200)]:
            current=root/name;out=root/f'render_{name}_{budget}'
            execute(f'render_{name}_{budget}',[sys.executable,str(current/'render_live_gpu_feedback.py'),
                '--ct-record',ct,'--output',str(out),'--budget',str(budget)],current,render_env)
            record['renders'].append(dict(variant=name,budget=budget,
                path=str(out/'01-真实GPU父反馈与像素交付完整记录.json'),
                sha256=sha(out/'01-真实GPU父反馈与像素交付完整记录.json')));save()
        record['status']='completed';save()
    except Exception as error:
        record.update(status='failed',error=repr(error));save();raise


if __name__=='__main__':main()
