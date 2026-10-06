"""从首个原生布尔失败的实际父网格隔离排序与工具顺序，失败不发布。"""
import argparse,hashlib,json,subprocess,sys
from datetime import datetime,timezone,timedelta
from pathlib import Path
import numpy as np
import trimesh


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('root',type=Path)
    parser.add_argument('--child',type=Path);parser.add_argument('--certified-sort',type=int,choices=[0,1]);parser.add_argument('--reverse-tools',type=int,choices=[0,1]);args=parser.parse_args()
    root=args.root;sys.path.insert(0,str(root/'workers'))
    if args.child:
        from resident_batch_engine import ResidentBatchEngine
        from geogram_batch_memory import GeogramBatchMemory
        from exact_mesh_memory import ExactMeshMemory
        case=json.loads((args.child/'case.json').read_text(encoding='utf-8'))
        path=root/case['parent_path'];assert sha(path)==case['parent_sha256']
        with np.load(path) as data:v,f=data['vertices'].copy(),data['faces'].copy()
        full=ExactMeshMemory();assert full.audit(v,f)['embedded_closed'];tools=[]
        for item in case['tools']:
            path=root/'inputs'/item['mesh'];assert sha(path)==item['sha256']
            mesh=trimesh.load(path,process=False);tv,tf=np.asarray(mesh.vertices),np.asarray(mesh.faces)
            assert full.audit(tv,tf)['embedded_closed'];tools.append((tv,tf))
        if args.reverse_tools:tools.reverse()
        engine=ResidentBatchEngine(v,f,quality_enabled=False);engine.api.close()
        class DirectBoolean:
            def __init__(self):self.api=GeogramBatchMemory()
            def difference_batch(self,v,f,tools,**kwargs):
                # 输入始终独立完整认证；该开关在本多操作数例只切换作者排序与候选固定排序。
                return self.api.difference_batch(v,f,tools,certified_operands=bool(args.certified_sort))
            def close(self):pass
        engine.api=DirectBoolean()
        try:detail,arrays=engine.step(tools)
        finally:engine.close()
        checks=[]
        for kind,values in arrays.items():
            if values is None:continue
            path=args.child/(kind+'.npz');np.savez_compressed(path,vertices=values[0],faces=values[1],bits=values[2])
            checks.append(dict(kind=kind,file_sha256=sha(path),check=full.audit(values[0],values[1])))
        if detail['published']:assert all(item['check']['embedded_closed'] for item in checks if item['kind'] in ('source','output'))
        (args.child/'result.json').write_text(json.dumps(dict(detail=detail,arrays=checks),ensure_ascii=False,indent=2),encoding='utf-8')
        return
    report=json.loads((root/'03-完整批量父反馈记录.json').read_text(encoding='utf-8'))
    assert report['status']=='completed_with_recorded_failures'
    run=next(item for item in report['runs'] if any(row['status']=='boolean_execution_failed' for row in item['rows']))
    failed=next(row for row in run['rows'] if row['status']=='boolean_execution_failed')
    parent_step=failed['update']-1;saved=json.loads((root/run['label']/'02-实际保存清单.json').read_text(encoding='utf-8'))
    parent=next(item for item in saved if item['update']==parent_step and item['kind']=='output')
    assert parent['array_sha256']==failed['parent_array_sha256']
    route=next(item for item in json.loads((root/'manifest.json').read_text(encoding='utf-8'))['routes'] if run['label']==item['id']+'_candidate')
    tools=[route['prefix_tools'][i] for i in failed['event_steps']]
    assert [item['sha256'] for item in tools]==failed['tool_sha256']
    output=root/'boolean_failure_isolation';output.mkdir(exist_ok=False);results=[]
    record=dict(time_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat(),status='running',worker_sha256=sha(__file__),
        source_report_sha256=sha(root/'03-完整批量父反馈记录.json'),failed_update=failed['update'],event_steps=failed['event_steps'],rows=results,
        scope='同一实际已认证父网格及全部原工具，两个排序与工具正逆序各三轮；隔离结果不接原父链、不发布')
    for flag in (1,0):
        for reverse in (0,1):
            for repeat in range(3):
                folder=output/f'sort{flag}_reverse{reverse}_r{repeat}';folder.mkdir()
                (folder/'case.json').write_text(json.dumps(dict(parent_path=parent['path'],parent_sha256=parent['file_sha256'],tools=tools),ensure_ascii=False,indent=2),encoding='utf-8')
                process=subprocess.run([sys.executable,'-u',__file__,str(root),'--child',str(folder),'--certified-sort',str(flag),'--reverse-tools',str(reverse)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
                (folder/'actual_stdout.log').write_text(process.stdout,encoding='utf-8')
                detail=json.loads((folder/'result.json').read_text(encoding='utf-8')) if (folder/'result.json').exists() else None
                item=dict(certified_sort=bool(flag),reverse_tools=bool(reverse),repeat=repeat,exit_code=process.returncode,result=detail)
                results.append(item);(output/'01-原生失败排序隔离.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
                print(json.dumps(dict(sort=flag,reverse=reverse,repeat=repeat,exit_code=process.returncode,accepted=detail['detail']['published'] if detail else None)),flush=True)
    record.update(status='completed',finished_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat())
    (output/'01-原生失败排序隔离.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':main()
