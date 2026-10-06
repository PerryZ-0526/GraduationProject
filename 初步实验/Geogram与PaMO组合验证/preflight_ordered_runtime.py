"""独立加载封存运行依赖，预检不连接GPU或打开保留维护结果。"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
from audit_followup_candidate import sha256
from freeze_ordered_evaluation import runtime_sources,runtime_source_path
from run_geometry_study import now,save


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--development',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    root=Path(__file__).resolve().parent
    args.output.mkdir(exist_ok=False)
    runtime=args.output/'运行入口与依赖';runtime.mkdir()
    record=json.loads((args.development/'01-反馈执行与独立审计.json').read_text(encoding='utf-8'))
    entry=record['environment'].get('evaluation_entry_file','run_ordered_reference_feedback.py')
    if entry not in ('run_ordered_reference_feedback.py','run_active_patch_feedback.py'):
        raise ValueError('未登记可封存的实际反馈入口')
    seeds=[entry]+[p.name for p in args.development.iterdir() if p.suffix in ('.py','.cpp')]
    files=[]
    for name in runtime_sources(root,seeds):
        original=runtime_source_path(root,name)
        target=runtime/name;target.write_bytes(original.read_bytes())
        files.append(dict(file=name,sha256=sha256(target),source_path=str(original.resolve())))
    # 子进程只导入登记的实际入口；不调用main或构造远端引擎。
    code='''import pathlib,json,sys,importlib
entry=importlib.import_module(sys.argv[1])
from run_constrained_batch import HERE
root=pathlib.Path.cwd()
local={name:str(pathlib.Path(module.__file__).resolve()) for name,module in sys.modules.items()
    if getattr(module,'__file__',None) and pathlib.Path(module.__file__).resolve().is_relative_to(root)}
assert HERE.resolve()==root.resolve()
print(json.dumps(dict(here=str(HERE),modules=local,entry=str(entry.__file__)),ensure_ascii=False))
'''
    result=subprocess.run([sys.executable,'-c',code,Path(entry).stem],cwd=runtime,capture_output=True,text=True,encoding='utf-8')
    report=dict(time_beijing=now(),files=files,returncode=result.returncode,stdout=result.stdout,stderr=result.stderr,
        scope='封存依赖独立加载预检；不连接GPU、不释放评价或打开维护输出')
    save(args.output/'01-依赖封存与独立加载预检.json',report)
    print('files',len(files),'exit',result.returncode)
    if result.stderr:
        print(result.stderr[-2000:])
    raise SystemExit(result.returncode)
