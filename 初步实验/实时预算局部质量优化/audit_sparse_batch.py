"""重载活动邻接保存对象，核对源码、父输入、操作和总预算分层。"""
import argparse
from datetime import datetime,timezone,timedelta
from fractions import Fraction
import hashlib
import json
from math import nextafter,inf
from pathlib import Path
import numpy as np
import trimesh
from benchmark import quality
from local_guard import plane_bound


def outward_sum(values):
    exact=sum((Fraction.from_float(x) for x in values),Fraction(0));value=float(exact)
    while Fraction.from_float(value)<exact:value=nextafter(value,inf)
    return value


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',type=Path,required=True);parser.add_argument('--output',type=Path);args=parser.parse_args()
    root=args.root;sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    manifest=json.loads((root/'02-输入与研究预算冻结.json').read_text(encoding='utf-8'))
    freeze=json.loads((root/'03-执行源码冻结.json').read_text(encoding='utf-8'))
    variants=manifest['protocol']['variants']
    for name,digest in freeze.items():assert sha(root/name)==digest
    summary=[];saved=[];controls=[];preparation_pairs=[];observations=[]
    cases={x['id']:x for x in manifest['cases']}
    for case in cases.values():assert sha(root/case['file'].replace('\\','/'))==case['sha256']
    for backend in ('cpu','cuda'):
        record_path=root/backend/'01-完整准备预算与保存对象记录.json'
        record=json.loads(record_path.read_text(encoding='utf-8'))
        assert record['status']=='completed_with_recorded_outcomes' and len(record['rows'])==len(cases)*3*4*len(variants)
        assert record['source_sha256']==freeze and record['manifest_sha256']==sha(root/'02-输入与研究预算冻结.json')
        assert len(record['controls'])==len(cases)
        if manifest['protocol'].get('benchmark_entry') in ('benchmark_targeted.py','benchmark_native.py'):
            assert all(c['lazy_candidates_equal_to_full'] for c in record['controls'])
        else:
            assert all(c['queue_and_candidates_equal'] and c['first_batch_operations_equal'] for c in record['controls'])
        controls.extend(dict(backend=backend,**c) for c in record['controls']);observations.extend(record['gpu_observations'])
        sources={x['case']:json.loads(x['stdout']) for x in record['sources'] if x['returncode']==0}
        assert len(sources)==len(cases)
        # 每个后端、来源、轮次、预算、方法只允许一条记录，不能靠重复填充分母。
        keys={(x['case'],x['round'],x['total_budget_ms'],x['variant']) for x in record['rows']}
        expected={(c,n,b,v) for c in cases for n in range(3) for b in (20,50,100,200) for v in variants}
        assert keys==expected
        index={(x['case'],x['round'],x['total_budget_ms'],x['variant']):x for x in record['rows']}
        for key in keys:
            if key[-1]=='sparse':
                full=index[key[:-1]+('full',)];sparse=index[key]
                preparation_pairs.append(dict(backend=backend,case=key[0],round=key[1],budget_ms=key[2],full_ms=full['preparation_ms'],sparse_ms=sparse['preparation_ms']))
        for row in record['rows']:
            assert row['vertices_unchanged'] and row['outside_faces_unchanged'] and row['labels_unchanged']
            if 'output' not in row:continue
            data=np.load(root/cases[row['case']]['file'].replace('\\','/'))
            v,f,bits,active=[data[k] for k in ('vertices','faces','bits','active')]
            output=root/backend/row['output'];assert sha(output)==row['sha256']
            mesh=trimesh.load(output,process=False);work=f.copy();bounds=[]
            for op in row['operations']:
                owners=op['faces'];assert np.array_equal(work[owners],op['before']) and all(active[i] for i in owners) and bits[owners[0]]==bits[owners[1]]
                first,second=op['before'];shared=set(first)&set(second)
                a,b=next((first[k],first[(k+1)%3]) for k in range(3) if first[k] in shared and first[(k+1)%3] in shared)
                c=next(x for x in first if x not in shared);d=next(x for x in second if x not in shared)
                proof=plane_bound(v[[a,b,c,d]],manifest['protocol']['local_error_mm']);assert proof is not None
                assert proof['height_squared_numerator']==op['geometry']['height_squared_numerator'] and proof['height_squared_denominator']==op['geometry']['height_squared_denominator']
                assert Fraction.from_float(op['geometry']['error_upper_mm'])**2>=4*Fraction(int(proof['height_squared_numerator']),int(proof['height_squared_denominator']))
                work[owners]=op['after'];bounds.append(op['geometry']['error_upper_mm'])
            assert np.array_equal(v,mesh.vertices) and np.array_equal(work,mesh.faces) and np.array_equal(f[~active],mesh.faces[~active])
            q=quality(mesh.vertices,mesh.faces);assert q['invalid']==row['after']['invalid']
            for t in ('10','5','1'):
                assert q[t]['count']==row['after'][t]['count'] and abs(q[t]['area_fraction']-row['after'][t]['area_fraction'])<=1e-14
            result=row['embedding'];assert result['returncode']==0
            embedding=json.loads(result['stdout']);source=sources[row['case']]
            saved.append(dict(backend=backend,variant=row['variant'],case=row['case'],budget_ms=row['total_budget_ms'],sha256=row['sha256'],operation_replay=True,
                vertices_and_outside_unchanged=True,embedded_closed=embedding['embedded_closed'],source_self_intersection_pairs=source['self_intersection_pairs'],output_self_intersection_pairs=embedding['self_intersection_pairs'],
                input_invalid_faces=row['before']['invalid'],output_invalid_faces=q['invalid'],cumulative_local_error_upper_mm=outward_sum(bounds)))
        for variant in variants:
            for budget in (20,50,100,200):
                rows=[x for x in record['rows'] if x['variant']==variant and x['total_budget_ms']==budget]
                valid=[x for x in rows if sources[x['case']]['embedded_closed'] and x['before']['invalid']==0]
                total=[x['total_elapsed_ms'] for x in rows];prep=[x['preparation_ms'] for x in rows]
                summary.append(dict(backend=backend,variant=variant,budget_ms=budget,events=len(rows),total_mean_ms=float(np.mean(total)),total_p95_ms=float(np.percentile(total,95)),total_p99_ms=float(np.percentile(total,99)),total_max_ms=max(total),
                    total_overruns=sum(x['total_budget_overrun'] for x in rows),preparation_mean_ms=float(np.mean(prep)),preparation_p95_ms=float(np.percentile(prep,95)),adopted_flips=sum(x['accepted'] for x in rows),quality_improved_events=sum(x['after']['10']['count']<x['before']['10']['count'] for x in rows),
                    valid_input_events=len(valid),valid_input_adopted_flips=sum(x['accepted'] for x in valid),valid_input_quality_improved_events=sum(x['after']['10']['count']<x['before']['10']['count'] for x in valid)))
    report=dict(time_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat(),status='completed_with_recorded_outcomes',events=len(cases)*3*4*len(variants)*2,summary=summary,controls=controls,preparation_pairs=preparation_pairs,gpu_observations=observations,saved=saved,
        saved_replay_verified=len(saved),embedded_outputs=sum(x['embedded_closed'] for x in saved),embedded_and_area_valid_outputs=sum(x['embedded_closed'] and x['output_invalid_faces']==0 for x in saved),
        exact_motion_certified=False,continuous_cutting_tested=False,display_latency_tested=False,goal_complete=False)
    # 重复复审另存终态，不覆盖此前证据及其真实生成时间。
    output=args.output or root/'04-保存重放与总预算完整复审.json'
    if output.exists():raise FileExistsError(output)
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('controls','preparation_pairs','gpu_observations','saved')},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
