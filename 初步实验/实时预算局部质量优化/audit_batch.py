"""独立重载保存输出、重放操作并汇总预算曲线，保留全部失败。"""
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
    exact=sum((Fraction.from_float(x) for x in values),Fraction(0))
    result=float(exact)
    while Fraction.from_float(result)<exact:result=nextafter(result,inf)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',type=Path,required=True);args=parser.parse_args()
    root=args.root;manifest=json.loads((root/'02-输入与研究预算冻结.json').read_text(encoding='utf-8'))
    summary=[];saved=[]
    for mode in ('cpu','cuda'):
        record=json.loads((root/mode/'01-完整预算与保存对象记录.json').read_text(encoding='utf-8'))
        assert record['status']=='completed_with_recorded_outcomes' and len(record['rows'])==252
        assert record['method_sha256']==hashlib.sha256(Path(__file__).with_name('budget_flip.py').read_bytes()).hexdigest()
        assert record['manifest_sha256']==hashlib.sha256((root/'02-输入与研究预算冻结.json').read_bytes()).hexdigest()
        for row in record['rows']:
            if row['round']!=0:continue
            case=next(c for c in manifest['cases'] if c['id']==row['case'])
            data=np.load(root/case['file'].replace('\\','/'));v,f,bits,active=[data[k] for k in ('vertices','faces','bits','active')]
            output=root/mode/row['output'];assert hashlib.sha256(output.read_bytes()).hexdigest()==row['sha256']
            mesh=trimesh.load(output,process=False);work=f.copy();bounds=[]
            for op in row['operations']:
                ids=op['faces'];assert np.array_equal(work[ids],op['before']);assert all(active[i] for i in ids);assert bits[ids[0]]==bits[ids[1]]
                # 从原有向边恢复四点编号，独立重算共同像和有理数高度。
                a,b,c=op['before'][0];tri=op['before'][1];shared=set(op['before'][0])&set(tri)
                a,b=next((op['before'][0][k],op['before'][0][(k+1)%3]) for k in range(3) if op['before'][0][k] in shared and op['before'][0][(k+1)%3] in shared)
                c=next(x for x in op['before'][0] if x not in shared);d=next(x for x in tri if x not in shared)
                proof=plane_bound(v[[a,b,c,d]],manifest['protocol']['local_error_mm']);assert proof is not None
                assert op['geometry']['height_squared_numerator']==proof['height_squared_numerator'] and op['geometry']['height_squared_denominator']==proof['height_squared_denominator']
                assert Fraction.from_float(op['geometry']['error_upper_mm'])**2>=4*Fraction(int(proof['height_squared_numerator']),int(proof['height_squared_denominator']))
                work[ids]=op['after'];bounds.append(op['geometry']['error_upper_mm'])
            assert np.array_equal(work,mesh.faces) and np.array_equal(v,mesh.vertices) and np.array_equal(f[~active],mesh.faces[~active])
            after=quality(mesh.vertices,mesh.faces)
            # 面数和分类逐项相同；平台归约的面积比例只核对舍入误差，不改几何或质量采用规则。
            assert after['faces']==row['after']['faces'] and after['invalid']==row['after']['invalid']
            for threshold in ('10','5','1'):
                assert after[threshold]['count']==row['after'][threshold]['count'] and after[threshold]['fraction']==row['after'][threshold]['fraction']
            area_delta=max(abs(after[t]['area_fraction']-row['after'][t]['area_fraction']) for t in ('10','5','1'))
            assert area_delta<=1e-14
            embedding=row.get('embedding',{});parsed=json.loads(embedding['stdout']) if embedding.get('returncode')==0 else {}
            saved.append(dict(backend=mode,case=row['case'],budget_ms=row['budget_ms'],output=row['output'],sha256=row['sha256'],operation_replay=True,
                vertices_and_outside_unchanged=True,saved_quality_counts_equal=True,saved_area_fraction_delta=area_delta,embedded_closed=parsed.get('embedded_closed',False),input_invalid_faces=row['before']['invalid'],output_invalid_faces=after['invalid'],
                cumulative_local_error_upper_mm=outward_sum(bounds),raw_float_sum_preserved_as_diagnostic=row['local_error_upper_sum_mm']))
        for budget in manifest['protocol']['budgets_ms']:
            rows=[x for x in record['rows'] if x['budget_ms']==budget];times=[x['elapsed_ms'] for x in rows];prep=[x['preparation_ms'] for x in rows]
            summary.append(dict(backend=mode,budget_ms=budget,events=len(rows),adopted_flips=sum(x['accepted'] for x in rows),quality_improved_events=sum(x['after']['10']['count']<x['before']['10']['count'] for x in rows),
                mean_ms=float(np.mean(times)),p95_ms=float(np.percentile(times,95)),p99_ms=float(np.percentile(times,99)),max_ms=max(times),budget_overruns=sum(x['budget_overrun'] for x in rows),
                preparation_mean_ms=float(np.mean(prep)),preparation_p95_ms=float(np.percentile(prep,95)),prepared_plus_maintenance_p95_ms=float(np.percentile([x['prepared_and_step_ms'] for x in rows],95))))
    report=dict(time_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat(),summary=summary,saved=saved,saved_count=len(saved),embedded_count=sum(x['embedded_closed'] for x in saved),
        replay_verified=len(saved),continuous_cutting_tested=False,display_latency_tested=False,hard_realtime_proven=False)
    (root/'05-保存重放复审与预算曲线.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='saved'},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
