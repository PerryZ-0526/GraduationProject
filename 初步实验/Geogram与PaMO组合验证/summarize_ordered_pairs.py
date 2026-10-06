"""重算三源三轮四方法所有返回对象的质量，失败保留完整分母。"""
import argparse
from collections import Counter
import json
from pathlib import Path
import trimesh
from audit_followup_candidate import quality_distribution, sha256
from run_geometry_study import now, save


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    record_path=args.output/'01-三源三轮四方法同输入比较.json'
    audit_path=args.output/'02-三源三轮完整分母与保存对象复审.json'
    record=json.loads(record_path.read_text(encoding='utf-8'))
    audit=json.loads(audit_path.read_text(encoding='utf-8'))
    if record['status']!='completed_with_recorded_outcomes' or audit['record_sha256']!=sha256(record_path) or audit['artifacts']!=36:
        raise ValueError('完整36条终态和保存复审未成立')
    # 保留抽样初审与全顶点复审的拒绝差异，不把原复审失败数字改写为通过。
    discrepancies=[r for r in audit['rows'] if not r['passed']]
    if any(r['kind']!='returned_output' or r['recorded_status']!='accepted_sampled'
        or r['recomputed_accepted'] or r['geometry']['probe_max_mm']<=.1 for r in discrepancies):
        raise ValueError('存在不能归因为全顶点几何超限的复审差异')
    audited={(r['case'],r['round'],r['method']):r for r in audit['rows']}
    result=dict(time_beijing=now(),record_sha256=sha256(record_path),audit_sha256=sha256(audit_path),rows=[],methods={},
        audit_decision_matches=audit['passed'],audit_artifacts=audit['artifacts'],decision_discrepancies=discrepancies,
        scope='已见三源各三轮，全网格面与面积分母；保留初审状态，最终接受按保存复审；所有返回对象含拒绝，执行失败无网格；不作新输入泛化或速度结论')
    for row in record['rows']:
        case,round_id,method=row['case'],row['round'],row['declared_method']
        source_path=args.output/(case+'_input')/'clean_source.obj'
        if sha256(source_path)!=row['same_input_sha256']['source.obj']:
            raise ValueError('实际同次源变化')
        item=dict(case=case,round=round_id,method=method,status=row['status'],
            source=quality_distribution(trimesh.load(source_path,process=False)))
        evidence=audited[case,round_id,method]
        if evidence['kind']=='returned_output':
            output=Path(row['artifact_directory'])/'candidate.obj'
            if sha256(output)!=row['output_sha256']:
                raise ValueError('返回对象摘要变化')
            item.update(output=quality_distribution(trimesh.load(output,process=False)),
                accepted=evidence['recomputed_accepted'],output_sha256=sha256(output))
        else:
            item['output_unavailable_reason']=row['status']
        result['rows'].append(item)
    for method in ('full','global','spatial','boolean'):
        rows=[r for r in result['rows'] if r['method']==method]
        result['methods'][method]=dict(planned=len(rows),statuses=dict(Counter(r['status'] for r in rows)),
            returned=sum('output' in r for r in rows),accepted=sum(r.get('accepted',False) for r in rows))
    save(args.output/'03-三源三轮完整分母质量统计.json',result)
    print(result['methods'])
