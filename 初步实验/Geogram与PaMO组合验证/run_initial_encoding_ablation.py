"""冻结实际维护源的交错配对消融，只比较初态编码锚点规则。"""
import argparse
import json
from pathlib import Path
import random
import shlex
from run_precondition_capture import CaptureEngine
from run_initial_encoding_projection import InitialEncodingEngine
from preserved_feedback_gate import audit_preserved_candidate
from run_geometry_study import save, now, retrieve
from audit_followup_candidate import sha256


def schedule(case_ids, rounds, seed):
    tasks=[(case, round_id, method) for case in case_ids for round_id in range(rounds)
        for method in ('without_initial_anchors','with_initial_anchors')]
    random.Random(seed).shuffle(tasks)
    return tasks


def validate_inputs(package, manifest):
    for case in manifest['cases']:
        for name in ('source','labels','tool'):
            path=(package/case[name]).resolve()
            if not path.is_relative_to(package.resolve()) or sha256(path) != case[name+'_sha256']:
                raise ValueError('冻结消融输入变化或越界')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cases',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--port',type=int,required=True)
    args=parser.parse_args()
    manifest_path=args.cases/'01-冻结清单.json'
    manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    validate_inputs(args.cases,manifest)
    args.output.mkdir(exist_ok=False)
    methods={'without_initial_anchors':CaptureEngine,'with_initial_anchors':InitialEncodingEngine}
    engines={};record=dict(time_beijing=now(),status='running',published=False,rows=[],environment={},
        manifest_sha256=sha256(manifest_path), entry_sha256=sha256(Path(__file__)),
        scope='已见开发输入三轮随机交错，同源同工具同标签；共享GPU不作性能推断')
    tasks=schedule([case['id'] for case in manifest['cases']],3,20261005)
    record['schedule']=[dict(case=c,round=r,method=m) for c,r,m in tasks]
    path=args.output/'01-冻结源初态规则交错消融.json'
    try:
        for method, kind in methods.items():
            folder=args.output/method;folder.mkdir()
            engines[method]=kind(folder,args.port)
            record['environment'][method]=engines[method].setup()
        save(path,record)
        cases={case['id']:case for case in manifest['cases']}
        for case_id, round_id, method in tasks:
            case=cases[case_id];engine=engines[method]
            folder=engine.output/(case_id+'_r'+str(round_id))
            source,labels,tool=[args.cases/case[name] for name in ('source','labels','tool')]
            row=engine.run(source,labels,tool,'boolean',folder)
            row=audit_preserved_candidate(engine,source,tool,labels,folder,row)
            command=shlex.split(row['execution']['command'])
            remote=command[command.index('--output')+1]
            before_name='before_precondition.obj' if method=='without_initial_anchors' else 'before_projection.obj'
            # 原版前置拒绝也保存同次质量生成对象；不能用另一轮重生成替代。
            try:
                retrieve(engine.client,engine.sftp,remote+'/'+before_name,folder/before_name)
                row['before_sha256']=sha256(folder/before_name)
            except FileNotFoundError:
                row['before_available']=False
            row.update(case=case_id,round=round_id,variant=method,artifact_directory=str(folder.resolve()))
            record['rows'].append(row);save(path,record)
            print(case_id,round_id,method,row['status'],flush=True)
        pairs=[]
        for case_id in cases:
            for round_id in range(3):
                selected=[row for row in record['rows'] if row['case']==case_id and row['round']==round_id]
                old=next(row for row in selected if row['variant']=='without_initial_anchors')
                new=next(row for row in selected if row['variant']=='with_initial_anchors')
                pairs.append(dict(case=case_id,round=round_id,
                    same_uploaded_inputs=old.get('inputs_sha256')==new.get('inputs_sha256') and bool(old.get('inputs_sha256')),
                    same_before=old.get('before_sha256')==new.get('before_sha256') and bool(old.get('before_sha256')),
                    without_status=old['status'],with_status=new['status']))
        record.update(status='completed_with_recorded_outcomes',finished_beijing=now(),pairs=pairs)
        save(path,record)
    finally:
        for engine in engines.values():engine.close()
