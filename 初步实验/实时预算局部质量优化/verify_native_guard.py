"""在实际CT邻接查询和独立病态查询上逐项核对C++与原Python精确判定。"""
import argparse
from datetime import datetime,timezone,timedelta
import hashlib
import json
from pathlib import Path
from time import perf_counter
import numpy as np
from local_guard import LocalGuard,separated_except_shared
from native_guard import load_library,separated_native


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();load_library();queries=[];bindings=[]
    record_path=args.reference/'cpu/01-完整准备预算与保存对象记录.json'
    record=json.loads(record_path.read_text(encoding='utf-8'))
    for row in record['rows']:
        if row['variant']!='targeted_fast' or row['round']!=0 or row['total_budget_ms']!=200:continue
        path=args.reference/'inputs'/f'{row["case"]}.npz'
        data=np.load(path);v,f=data['vertices'],data['faces'].copy();guard=LocalGuard(v,f)
        bindings.append(dict(case=row['case'],input_sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
        for op in row['operations']:
            for tri in op['after']:
                points=v[tri]
                original=np.flatnonzero(np.all(guard.high>=points.min(0),axis=1)&np.all(guard.low<=points.max(0),axis=1))
                lo,hi=points.min(0),points.max(0)
                fast=np.flatnonzero((guard.high[:,0]>=lo[0])&(guard.high[:,1]>=lo[1])&(guard.high[:,2]>=lo[2])&
                    (guard.low[:,0]<=hi[0])&(guard.low[:,1]<=hi[1])&(guard.low[:,2]<=hi[2]))
                assert np.array_equal(original,fast)
                for other in original:
                    if other in op['faces']:continue
                    # 仅保留六点和共同实体身份，重新编号不会改变精确分离问题。
                    first,second=list(tri),list(f[other]);ids=sorted(set(first)|set(second));index={x:k for k,x in enumerate(ids)}
                    queries.append((v[ids],list(map(index.get,first)),list(map(index.get,second)),'实际CT查询'))
            f[op['faces']]=op['after'];guard.committed(op['faces'])
    actual=len(queries);rng=np.random.default_rng(2026100604)
    for scale in (1e-200,1e-100,1,1e100,1e200):
        for shared in range(4):
            for repeat in range(40):
                vertices=rng.normal(size=(6,3))*scale
                second=[0,1,2][:shared]+list(range(3,6))[:3-shared]
                queries.append((vertices,[0,1,2],second,'病态与共同实体控制'))
    # 共面接触、跨面、极细面及一个ULP的平面偏离，均需保持原判定结果。
    for z in (0,np.nextafter(0.0,1.0),1e-16,-1e-16,1):
        v=np.array([[0,0,0],[2,0,0],[0,2,0],[.2,.2,z],[.8,.2,z],[.2,.8,z]])
        queries.append((v,[0,1,2],[3,4,5],'共面与微小偏离控制'))
    timings={name:[] for name in ('python','native')};answers=[]
    for vertices,first,second,label in queries:
        result=[]
        for name,method in (('python',separated_except_shared),('native',separated_native)):
            start=perf_counter();result.append(method(vertices,first,second,start+10));timings[name].append((perf_counter()-start)*1000)
        assert result[0]==result[1],(label,vertices,first,second,result)
        answers.append(bool(result[0]))
    assert not separated_native(np.eye(6,3),[0,1,2],[3,4,5],perf_counter()-1)
    report=dict(time_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat(),status='passed',actual_ct_queries=actual,
        control_queries=len(queries)-actual,paired_queries=len(queries),all_answers_identical=True,expired_deadline_rejected=True,
        bbox_membership_identical=True,reference_record_sha256=hashlib.sha256(record_path.read_bytes()).hexdigest(),inputs=bindings,
        timing={name:dict(total_ms=sum(values),median_ms=float(np.median(values)),p95_ms=float(np.percentile(values,95)),max_ms=max(values)) for name,values in timings.items()},
        answer_sha256=hashlib.sha256(bytes(answers)).hexdigest(),static_query_control_only=True)
    assert not args.output.exists()
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(report,ensure_ascii=True))


if __name__=='__main__':main()
