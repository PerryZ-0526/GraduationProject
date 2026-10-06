"""不使用增量证书，全量重测真实保存对象并核对完整父链与四档质量分布。"""
import argparse
from datetime import datetime,timezone,timedelta
import hashlib,json
from pathlib import Path
import numpy as np
from exact_mesh_memory import ExactMeshMemory
from benchmark import quality


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True);args=p.parse_args()
    record_path=args.root/'01-真实父反馈四预算完整记录.json';sha=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()
    report=json.loads(record_path.read_text(encoding='utf-8'));assert report['status']=='completed'
    full=ExactMeshMemory();audits=[];summaries=[];objects={}
    def read(path,expected):
        assert sha(path)==expected
        if path not in objects:
            # 自身保存OBJ保留无引用顶点；逐行读取原索引才能复核真实翻边记录。
            vertices=[];facets=[]
            for line in Path(path).read_text(encoding='utf-8').splitlines():
                if line.startswith('v '):vertices.append([float(x) for x in line.split()[1:]])
                elif line.startswith('f '):facets.append([int(x)-1 for x in line.split()[1:]])
            v=np.asarray(vertices,dtype=np.float64);f=np.asarray(facets,dtype=np.int64)
            objects[path]=(v,f);check=full.audit(v,f);audits.append(dict(path=path,sha256=expected,check=check))
        return objects[path],next(a['check'] for a in audits if a['path']==path)
    for route in report['routes']:
        assert route['status']=='completed' and len(route['events'])==route['planned_events']==16
        parent=report['initial_sha256'];blocked=False;accepted=[];gains=[]
        for index,event in enumerate(route['events']):
            assert event['step']==index
            if event['status']=='blocked_by_previous_invalid_source':assert blocked;continue
            assert not blocked and event['parent_sha256']==parent and event['tool_sha256']==report['tool_sha256'][index]
            _,raw_check=read(event['raw_path'],event['raw_sha256'])
            (sv,sf),source_check=read(event['source_path'],event['source_sha256'])
            if event['status']=='source_rejected':blocked=True;continue
            assert event['status']=='published_verified' and source_check['embedded_closed']
            (v,f),output_check=read(event['output_path'],event['output_sha256']);assert output_check['embedded_closed']
            assert quality(v,f,0)==event['output_quality'] and quality(sv,sf,0)==event['source_quality']
            # 质量步骤固定全部顶点和来源面数；短边源处理在另一条证据链单独记录。
            np.testing.assert_array_equal(v,sv);assert len(f)==len(sf)
            changed=np.flatnonzero(np.any(f!=sf,axis=1));bits=np.load(Path(event['source_path']).with_name(f'e{index:02d}_source_bits.npy'))
            maintenance=event['maintenance'];op_faces=set()
            replay=sf.copy()
            if maintenance:
                for op in maintenance['operations']:
                    op_faces.update(op['faces'])
                    # 逐次匹配当时原面，不只核对改动面号属于某个记录。
                    np.testing.assert_array_equal(replay[op['faces']],op['before']);replay[op['faces']]=op['after']
            committed=bool(event['final_check'] and event['final_check']['embedded_closed'])
            np.testing.assert_array_equal(f,replay if committed else sf)
            assert set(changed).issubset(op_faces)
            assert event['budget_overrun']==(event['maintenance_total_ms']>route['budget_ms'])
            parent=event['output_sha256'];accepted.append(event)
            gains.append(dict(step=index,changed_faces=len(changed),raw_embedding_valid=raw_check['embedded_closed'],
                source_to_output={str(t):dict(count=event['source_quality'][str(t)]['count']-event['output_quality'][str(t)]['count'],
                    area_fraction=event['source_quality'][str(t)]['area_fraction']-event['output_quality'][str(t)]['area_fraction']) for t in (10,5,1)}))
        assert len(accepted)==route['valid_published']
        totals=np.array([e['maintenance_total_ms'] for e in accepted]);whole=np.array([e['cut_and_maintenance_ms'] for e in accepted])
        summaries.append(dict(budget_ms=route['budget_ms'],planned=16,published=len(accepted),
            rejected=sum(e['status']=='source_rejected' for e in route['events']),blocked=sum(e['status']=='blocked_by_previous_invalid_source' for e in route['events']),
            within_budget=sum(not e['budget_overrun'] for e in accepted),maintenance_mean_ms=float(totals.mean()),
            maintenance_p95_ms=float(np.percentile(totals,95)),cut_and_maintenance_mean_ms=float(whole.mean()),
            cut_and_maintenance_p95_ms=float(np.percentile(whole,95)),
            quality_flips=sum(e['maintenance']['accepted'] if e['maintenance'] else 0 for e in accepted),gains=gains))
    result=dict(time_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat(),record_sha256=sha(record_path),
        status='completed',all_saved_published_and_sources_embedded=True,all_parent_chains_valid=True,
        full_audited_objects=len(audits),audits=audits,summaries=summaries)
    output=args.root/'02-完整保存全量精确复审与四预算统计.json';assert not output.exists()
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(summaries,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
