"""同一保存源交错对拍紧凑短边修复，核对候选、包围盒、操作及全量嵌入。"""
import argparse
from datetime import datetime,timezone,timedelta
import hashlib,json
from pathlib import Path
from time import perf_counter
import numpy as np
from short_edge_scan import prepare_short_edges
from short_edge_repair_reference import repair_short_edges as reference
from short_edge_repair import repair_short_edges as compact
from native_guard import separated_native
from exact_mesh_memory import ExactMeshMemory
from numeric_input import check_and_boxes
from covered_zero_cleanup import clean_arrays


def load_obj(path):
    # 保留未引用点和原索引，不能通过通用加载器清理后再对拍。
    vertices=[];faces=[]
    for line in Path(path).read_text().splitlines():
        if line.startswith('v '):vertices.append([float(x) for x in line.split()[1:]])
        elif line.startswith('f '):faces.append([int(x)-1 for x in line.split()[1:]])
    return np.array(vertices),np.array(faces,dtype=np.int64)


def original_scan(v,f,tolerance):
    a,b,c=(v[f[:,k]] for k in range(3))
    edges=np.concatenate((f[:,[0,1]],f[:,[1,2]],f[:,[2,0]]));edges.sort(axis=1)
    distances=np.linalg.norm(v[edges[:,0]]-v[edges[:,1]],axis=1)
    return np.minimum(np.minimum(a,b),c),np.maximum(np.maximum(a,b),c),np.unique(edges[distances<=tolerance],axis=0)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--batch',type=Path,required=True)
    p.add_argument('--initial',type=Path,required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    assert not args.output.exists();sha=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()
    record=json.loads((args.batch/'01-真实父反馈四预算完整记录.json').read_text())
    route=next(r for r in record['routes'] if r['budget_ms']==200)
    tolerance=1e-10;controls=[];rng=np.random.default_rng(2026100607)
    # 固定物理容差附近的边界、重复、负零及各尺度均用原实现作为候选集合对照。
    for scale in (1e-200,1e-100,1e-10,1,1e100):
        v=rng.normal(size=(99,3))*scale;f=rng.integers(0,len(v),(130,3),dtype=np.int64)
        v[1]=v[0];v[2]=[-0.,0.,0.];v[3]=[tolerance,0,0]
        v[4]=[np.nextafter(tolerance,np.inf),0,0];v[5]=[np.nextafter(tolerance,0),0,0]
        f[:3]=[[2,3,4],[2,4,5],[0,1,2]]
        old=original_scan(v,f,tolerance);new=prepare_short_edges(v,f,tolerance)
        for a,b in zip(old,new):np.testing.assert_array_equal(a,b)
        controls.append(dict(scale=scale,candidates=len(new[2]),identical=True))
    full=ExactMeshMemory();rows=[];parent,_=load_obj(args.initial)
    for event in route['events']:
        assert event['status']=='published_verified'
        raw_path=Path(event['raw_path']);bits_path=raw_path.with_name(raw_path.stem+'_bits.npy')
        v,f=load_obj(raw_path);bits=np.load(bits_path)
        if check_and_boxes(v,f,0)[0]:v,f,bits,_=clean_arrays(v,f,bits)
        old=original_scan(v,f,tolerance);new=prepare_short_edges(v,f,tolerance)
        for a,b in zip(old,new):np.testing.assert_array_equal(a,b)
        pairs=[]
        for repeat in range(3):
            results={}
            for name in (['reference','compact'] if repeat%2==0 else ['compact','reference']):
                function=reference if name=='reference' else compact
                start=perf_counter();result=function(v,f,bits,parent,5000,separation_check=separated_native)
                results[name]=(result,(perf_counter()-start)*1000)
            a,b=results['reference'][0],results['compact'][0]
            for x,y in zip(a[:3],b[:3]):np.testing.assert_array_equal(x,y)
            for key in ['operations','rejections','candidate_edges','surviving_original_faces','geometry_upper_sum_mm',
                        'sum_of_outward_bounds_numerator','sum_of_outward_bounds_denominator']:
                assert a[3][key]==b[3][key],(event['step'],key)
            pairs.append(dict(repeat=repeat,reference_ms=results['reference'][1],compact_ms=results['compact'][1],
                reference_preparation_ms=a[3]['preparation_ms'],compact_preparation_ms=b[3]['preparation_ms']))
        audit=full.audit(b[0],b[1]);assert audit['embedded_closed']
        rows.append(dict(step=event['step'],raw_sha256=sha(raw_path),
            bits_sha256=sha(bits_path),candidates=len(new[2]),operations=len(b[3]['operations']),pairs=pairs,full_audit=audit))
        parent,_=load_obj(event['output_path'])
        print(event['step'],pairs[-1]['reference_ms'],pairs[-1]['compact_ms'],flush=True)
    report=dict(time_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat(),status='completed',controls=controls,rows=rows,
        method_sha256={name:sha(Path(__file__).with_name(name)) for name in ['short_edge_repair.py',
            'short_edge_repair_reference.py','short_edge_scan.py','native_short_edge_scan.cpp','libshort_edge_scan.so',Path(__file__).name]},
        pairs=len(rows)*3,all_outputs_operations_and_bounds_identical=True,
        scope='同保存源足量预算逐项等同对拍；不代替真实预算连续父反馈或显示计时')
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps(dict(pairs=report['pairs'],reference_median_ms=float(np.median([p['reference_ms'] for r in rows for p in r['pairs']])),
        compact_median_ms=float(np.median([p['compact_ms'] for r in rows for p in r['pairs']])))))


if __name__=='__main__':main()
