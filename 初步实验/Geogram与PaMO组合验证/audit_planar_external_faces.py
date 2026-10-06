"""只读核对共面候选的原活动域外有向面集合，区分顶点固定与三角化保持。"""
import argparse
import hashlib
import json
from pathlib import Path
import trimesh
from audit_followup_candidate import sha256
from constrained_quality import fixed_surface_contract
from locality_masks import make_masks
from recheck_completed_preserved_route import require_complete_route
from run_geometry_study import now,save


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('prepared','output','result'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--route')
    args=parser.parse_args()
    if args.result.exists():
        raise FileExistsError(args.result)
    raw=(args.output/'01-反馈执行与独立审计.json').read_bytes()
    record=json.loads(raw)
    manifest_path=args.prepared/'01-完整范围冻结清单.json'
    if sha256(manifest_path)!=record['manifest_sha256']:
        raise ValueError('完整输入清单与同次记录不符')
    routes=[r for r in json.loads(manifest_path.read_text(encoding='utf-8'))['routes']
        if r['split']==record['split'] and (args.route is None or r['id']==args.route)]
    if not routes or (args.route is None and record['status']!='completed_with_recorded_failures'):
        raise ValueError('必须为终态完整批次或明确完整子路线')
    rows=[]
    for route in routes:
        for row in require_complete_route(record,route):
            if row['branch']!='candidate' or row['status']!='published_under_sampled_and_vertex_protocol':
                continue
            method=row['selected_method']
            if method not in ('boolean','expanded'):
                rows.append(dict(route=row['route'],event=row['event'],method=method,kind='full_fallback_without_local_contract'))
                continue
            stem=row['route']+'_'+row['event']+'_candidate'
            source_path=args.output/(stem+'_input')/'clean_source.obj'
            labels_path=source_path.with_name('clean_labels.json')
            output_path=args.output/(stem+'_'+method)/'candidate.obj'
            attempt=next(a for a in row['attempts'] if a['status']=='accepted_sampled')
            if sha256(source_path)!=attempt['inputs_sha256']['source.obj'] or sha256(labels_path)!=attempt['inputs_sha256']['labels.json'] or sha256(output_path)!=row['output_sha256']:
                raise ValueError('同次保存对象摘要不符')
            source=trimesh.load(source_path,process=False)
            output=trimesh.load(output_path,process=False)
            bits=json.loads(labels_path.read_text(encoding='utf-8'))['operand_bits']
            # 布尔模式只读取来源及面邻接，不使用工具或维护结果挑选活动面。
            active,fixed=make_masks(source,bits,None,'boolean',4 if method=='expanded' else 2,allow_shared=True)
            contract=fixed_surface_contract(source,output,active,fixed)
            rows.append(dict(route=row['route'],event=row['event'],method=method,kind='local_candidate',
                source_sha256=sha256(source_path),output_sha256=sha256(output_path),contract=contract,
                missing_external_faces=contract['external_faces']-contract['external_faces_retained']))
    tested=[r for r in rows if r['kind']=='local_candidate']
    result=dict(time_beijing=now(),record_sha256=hashlib.sha256(raw).hexdigest(),full_batch_status=record['status'],rows=rows,
        planned_events=sum(len(r['cutting_prefix_ids']) for r in routes),published_outputs=len(rows),
        local_outputs=len(tested),strict_external_face_contract_passed=sum(r['contract']['passed'] for r in tested),
        scope='原来源活动域外固定顶点及有向面集合只读诊断；不改变发布结论，不将面集合变化自动等同几何漂移')
    save(args.result,result)
    print('local',len(tested),'external face contracts',result['strict_external_face_contract_passed'])
