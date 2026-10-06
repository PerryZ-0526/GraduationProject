"""保留旧校验器零操作索引失败，只恢复同冻结算法尚未执行的完整批次。"""
import argparse
from datetime import datetime,timezone,timedelta
import hashlib,json,os
from pathlib import Path
import subprocess,sys


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True);args=p.parse_args()
    root=args.root.resolve();sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
    old_path=root/'01-缓存源认证完整GPU反馈执行记录.json';old=json.loads(old_path.read_text())
    assert old['status']=='failed' and old['stages'][-1]['name']=='existing_fixed_flip_controls'
    assert old['stages'][-1]['returncode']==1 and all(s['returncode']==0 for s in old['stages'][:-1])
    assert not old['trials'] and not old['renders']
    assert 'IndexError: list index out of range' in (root/'existing_fixed_flip_controls.log').read_text()
    pair=json.loads((root/'02-缓存精确源证书九十六配对完整核对.json').read_text());assert pair['pairs']==96
    controls=json.loads((root/'03-缓存证书完整正负控制.json').read_text());assert controls['all_decisions_identical']
    for name,expected in old['frozen_sources_and_libraries'].items():assert sha(root/name)==expected
    workers=root/'workers';base=Path(old['baseline']);target=root/'05-固定控制选择修正后完整GPU反馈执行记录.json';assert not target.exists()
    record=dict(time_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat(),status='running',baseline=str(base),
        failed_record_sha256=sha(old_path),frozen_sources_and_libraries=old['frozen_sources_and_libraries'],
        correction_source_sha256=sha(workers/'verify_fixed_flip_certificate_cached_control.py'),
        stages=[],trials=[],renders=[],gpu_shared=True,scope='只改校验器选择实际非零操作源；算法和全部分母不改，旧失败保留')
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
        execute('corrected_fixed_flip_controls',[sys.executable,str(workers/'verify_fixed_flip_certificate_cached_control.py'),
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
        rendering=base/'render_trials_retry2';render_env=dict(environment,PYTHONPATH=str(rendering/'python_deps'),
            LD_LIBRARY_PATH=str(rendering/'egl/usr/lib/x86_64-linux-gnu')+':'+environment.get('LD_LIBRARY_PATH',''),
            VTK_DEFAULT_OPENGL_WINDOW='vtkEGLRenderWindow')
        record['render_runtime_record_sha256']=sha(rendering/'01-私有GPU渲染依赖与完整反馈执行记录.json');save()
        for name,budget in [('reference_workers',100),('workers',100),('workers',200)]:
            current=root/name;out=root/f'render_{name}_{budget}'
            execute(f'render_{name}_{budget}',[sys.executable,str(current/'render_live_gpu_feedback.py'),
                '--ct-record',ct,'--output',str(out),'--budget',str(budget)],current,render_env)
            record['renders'].append(dict(variant=name,budget=budget,path=str(out/'01-真实GPU父反馈与像素交付完整记录.json'),
                sha256=sha(out/'01-真实GPU父反馈与像素交付完整记录.json')));save()
        record['status']='completed';save()
    except Exception as error:
        record.update(status='failed',error=repr(error));save();raise


if __name__=='__main__':main()
