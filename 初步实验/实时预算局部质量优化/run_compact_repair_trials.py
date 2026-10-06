"""另建私有短边修复版本，完成同源对拍后交错执行完整四预算GPU父反馈。"""
import argparse
from datetime import datetime,timezone,timedelta
import hashlib,json,os
from pathlib import Path
import shutil,subprocess,sys,zipfile


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--baseline',type=Path,required=True)
    p.add_argument('--root',type=Path,required=True);p.add_argument('--incoming',type=Path,required=True);args=p.parse_args()
    base,root=args.baseline.resolve(),args.root.resolve();assert base!=root and base.parent==root.parent
    root.mkdir(exist_ok=False);sha=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()
    assert json.loads((base/'gpu_diagnostic_01/01-完整GPU诊断执行记录.json').read_text())['status']=='completed'
    for name in ['reference_workers','workers']:shutil.copytree(base/'workers',root/name)
    with zipfile.ZipFile(args.incoming) as archive:archive.extractall(root/'incoming')
    new=root/'workers';shutil.copyfile(new/'short_edge_repair.py',new/'short_edge_repair_reference.py')
    for name in ['short_edge_scan.py','native_short_edge_scan.cpp','verify_compact_short_repair.py']:
        shutil.copyfile(root/'incoming'/name,new/name)
    shutil.copyfile(root/'incoming/short_edge_repair_compact.py',new/'short_edge_repair.py')
    code=(new/'verified_budget_feedback.py').read_text()
    before="'short_edge_repair.py','maintain_input.py'"
    assert code.count(before)==1
    # 实际新增依赖及原版修复字节一起绑定，不修改历史生成器或源版本。
    code=code.replace(before,"'short_edge_repair.py','short_edge_repair_reference.py','short_edge_scan.py','native_short_edge_scan.cpp','libshort_edge_scan.so','maintain_input.py'")
    (new/'verified_budget_feedback.py').write_text(code)
    record=dict(time_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat(),status='running',stages=[],trials=[],
        baseline=str(base),incoming_sha256=sha(args.incoming),gpu_shared=True,
        scope='仅改变必需短边修复准备和覆盖查询；原精确判据及连续失败分母保持；显示另行验证')
    target=root/'01-紧凑短边修复完整GPU批次执行记录.json'
    def save():
        temp=target.with_suffix('.tmp');temp.write_text(json.dumps(record,ensure_ascii=False,indent=2));temp.replace(target)
    def execute(name,argv,cwd=new):
        log=root/(name+'.log')
        with log.open('x') as stream:result=subprocess.run(argv,cwd=cwd,stdout=stream,stderr=subprocess.STDOUT)
        record['stages'].append(dict(name=name,argv=argv,returncode=result.returncode,log_sha256=sha(log)));save()
        assert result.returncode==0,(name,result.returncode)
    def gpu():
        result=subprocess.run(['nvidia-smi','--query-compute-apps=pid,process_name,used_memory','--format=csv,noheader'],capture_output=True,text=True)
        return dict(returncode=result.returncode,stdout=result.stdout,stderr=result.stderr)
    save();os.environ['LD_PRELOAD']='/usr/lib/x86_64-linux-gnu/libstdc++.so.6'
    try:
        execute('compile_scan',['g++','-std=c++17','-O3','-shared','-fPIC','-fno-fast-math','-ffp-contract=off','-frounding-math',
            str(new/'native_short_edge_scan.cpp'),'-o',str(new/'libshort_edge_scan.so')])
        for name in ['reference_workers','workers']:
            workers=root/name;identity=json.loads((workers/'build_identity.json').read_text())
            # 原库复制字节保持，仅重绑定私有工作器；Geogram底层库仍指向保留的原构建。
            for row in identity['libraries']:
                path=Path(row['path'])
                assert sha(path)==row['sha256']
                if path.parent==base/'workers':row['path']=str(workers/path.name)
            identity['copied_from_build_identity_sha256']=sha(base/'workers/build_identity.json')
            if name=='workers':identity['libraries'].append(dict(path=str(new/'libshort_edge_scan.so'),sha256=sha(new/'libshort_edge_scan.so')))
            (workers/'build_identity.json').write_text(json.dumps(identity,ensure_ascii=False,indent=2))
        frozen={str(path.relative_to(root)):sha(path) for name in ['reference_workers','workers']
                for path in (root/name).iterdir() if path.suffix in ['.py','.cpp','.so','.json']}
        record['frozen_sources_and_libraries']=frozen;save()
        execute('same_source_controls',[sys.executable,str(new/'verify_compact_short_repair.py'),
            '--batch',str(base/'gpu_diagnostic_01/feedback'),'--initial',str(base/'inputs/initial.obj'),
            '--output',str(root/'02-同源短边修复逐项对拍.json')])
        execute('existing_short_repair_controls',[sys.executable,'-m','unittest','test_short_edge_repair'])
        # 每个方法每轮从原初态开始，不能将节约的组件时间冒充整帧加速。
        for repeat in range(3):
            for name in (['reference_workers','workers'] if repeat%2==0 else ['workers','reference_workers']):
                for path,expected in frozen.items():assert sha(root/path)==expected
                workers=root/name;directory=root/f'r{repeat}_{name}';trial=dict(repeat=repeat,variant=name,gpu_before=gpu(),status='running')
                record['trials'].append(trial);save()
                execute(f'run_{repeat}_{name}',[sys.executable,str(workers/'verified_budget_feedback.py'),
                    '--ct-record',str(base/'inputs/ct_record.json'),'--output',str(directory),
                    '--fixed-flip-certificate','--early-quality-return','--edge-backend','cuda','--certified-operand-pairs'],workers)
                execute(f'audit_{repeat}_{name}',[sys.executable,str(workers/'audit_verified_budget_feedback.py'),'--root',str(directory)],workers)
                trial.update(status='completed',gpu_after=gpu(),record_sha256=sha(directory/'01-真实父反馈四预算完整记录.json'),
                    audit_sha256=sha(directory/'02-完整保存全量精确复审与四预算统计.json'));save()
        record['status']='completed';save()
    except Exception as error:
        record.update(status='failed',error=repr(error));save();raise


if __name__=='__main__':main()
