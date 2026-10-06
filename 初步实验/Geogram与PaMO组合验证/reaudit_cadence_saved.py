"""重新读取实际保存输出及累计参照，执行完整嵌入与双向距离复审。"""
import argparse
import json
from pathlib import Path
import trimesh
from audit_followup_candidate import sha256,quality_distribution
from preserved_feedback_gate import check_preserved_mesh
from run_cadence_feedback import Engine
from run_constrained_feedback import global_geometry
from run_geometry_study import now,save


def run(args):
    report=json.loads((args.batch/'03-批次环境与完整分母.json').read_text(encoding='utf-8'))
    if report['status']!='completed_with_recorded_outcomes':raise ValueError('尚无完整终态')
    records=[json.loads(x) for x in (args.batch/'04-逐刀真实父反馈记录.jsonl').read_text(encoding='utf-8').splitlines()]
    args.output.mkdir(exist_ok=False)
    engine=Engine(args.output,args.port)
    result=dict(time_beijing=now(),status='running',ledger_sha256=sha256(args.batch/'04-逐刀真实父反馈记录.jsonl'),
                script_sha256=sha256(Path(__file__)),rows=[])
    try:
        result['environment']=engine.setup()
        references={}
        # 先复审累计参照，不把存档里的通过字段直接当作本次证据。
        for folder in sorted(args.batch.glob('reference_*')):
            original=json.loads((folder/'01-独立累计工具参照.json').read_text(encoding='utf-8'))
            for position,row in enumerate(original['rows']):
                if row['status']!='reference_valid':continue
                source=folder/f'step_{position}'/'source.obj'
                if sha256(source)!=row['source_sha256']:raise ValueError('参照保存字节改变')
                mesh=trimesh.load(source,process=False)
                valid,metrics=check_preserved_mesh(engine,args.output/f'{folder.name}_step{position}',mesh,'reference')
                if not valid:raise ValueError('累计参照完整复审失败')
                references[(folder.name, row['event'])]=(mesh,metrics,row['source_sha256'])
        for folder in sorted(args.batch.glob('route*_round*_*_step*')):
            original=json.loads((folder/'audit.json').read_text(encoding='utf-8'))
            if 'candidate_sha256' not in original:continue
            path=folder/'candidate.obj'
            if sha256(path)!=original['candidate_sha256']:raise ValueError('候选保存字节改变')
            candidate=trimesh.load(path,process=False)
            target=args.output/folder.name
            valid,metrics=check_preserved_mesh(engine,target,candidate,'candidate')
            route_index=folder.name.split('_')[0][5:]
            reference,reference_metrics,reference_digest=references[(f'reference_{route_index}',original['event'])]
            geometry=global_geometry(candidate,reference)
            topology=(metrics['components'],metrics['euler_number'])==(reference_metrics['components'],reference_metrics['euler_number'])
            accepted=valid and topology and geometry['probe_max_mm']<=0.1
            consistent=accepted==(original['status']=='published')
            row=dict(folder=folder.name,original_status=original['status'],candidate_sha256=sha256(path),
                reference_sha256=reference_digest,valid=valid,topology_matches=topology,geometry=geometry,
                quality=quality_distribution(candidate),accepted=accepted,original_decision_consistent=consistent,metrics=metrics)
            result['rows'].append(row)
            save(args.output/'01-保存对象完整复审.json',result)
            if not consistent:raise ValueError('保存对象复审与实际发布决策不符')
        expected=sum('candidate_sha256' in r for r in records)
        if len(result['rows'])!=expected:raise ValueError('保存候选分母不完整')
        result.update(status='completed',finished_beijing=now(),checked_candidates=expected,
            published_reaudited=sum(r['accepted'] for r in result['rows']),checked_references=len(references))
        save(args.output/'01-保存对象完整复审.json',result)
        print('完整保存复审',expected,'发布',result['published_reaudited'],flush=True)
    finally:engine.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batch',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--port',type=int,required=True)
    run(parser.parse_args())
