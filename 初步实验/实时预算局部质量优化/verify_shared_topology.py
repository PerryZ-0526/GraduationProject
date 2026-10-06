"""同源交错核对邻接复用、动态覆盖、精确提交和失效证书，保留完整组件时间。"""
from pathlib import Path
from time import perf_counter
import datetime
import hashlib
import importlib.util
import json
import numpy as np
from certificate_activity_edges import SharedVerifiedMesh,CertificateActivityEdges
from exact_mesh_memory import ExactMeshMemory
from native_guard import NativeLocalGuard
from maintain_input import maintain_input
from targeted_budget_flip import LazyActivityEdges

ROOT=Path(__file__).resolve().parent.parent
OLD=Path('D:/GraduationProject实验输出/20261007_数组源证书本机完整反馈')
record=ROOT/'02-邻接复用九十六同源与完整提交核对.json';assert not record.exists()
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
spec=importlib.util.spec_from_file_location('sorted_edge_reference',ROOT/'reference_workers/maintain_input.py')
reference=importlib.util.module_from_spec(spec);spec.loader.exec_module(reference)
ct=json.loads((OLD/'inputs/ct_record.json').read_text(encoding='utf-8'))['routes'][0]['events']
full=ExactMeshMemory();rows=[];bindings=[];negative=[];edge_queries=0
report=dict(time_beijing=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),status='running',
    rows=rows,bindings=bindings,negative_controls=negative,method_sha256={p.name:sha(p) for p in (ROOT/'workers').iterdir() if p.is_file()})


def save():
    record.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')


def obj(path):
    vertices=[];faces=[]
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        if line.startswith('v '):vertices.append([float(x) for x in line.split()[1:]])
        elif line.startswith('f '):faces.append([int(x)-1 for x in line.split()[1:]])
    return np.asarray(vertices),np.asarray(faces,dtype=np.int64)


def rejects(name,fn):
    try:fn()
    except ValueError:negative.append(name);return
    raise AssertionError(name)


save()
try:
    prior=json.loads((OLD/'dll_r0_workers/01-真实父反馈四预算完整记录.json').read_text(encoding='utf-8'))
    for route in prior['routes']:
        if route['budget_ms'] not in [100,200]:continue
        for repeat in range(3):
            certificate=SharedVerifiedMesh()
            for event in route['events']:
                v,f=obj(event['source_path']);bits=np.load(Path(event['source_path']).with_name(f"e{event['step']:02d}_source_bits.npy"))
                assert sha(event['source_path'])==event['source_sha256']
                assert certificate.check(v,f,True)['embedded_closed']
                tv,_=obj(ct[event['step']]['tool_path']);assert sha(ct[event['step']]['tool_path'])==ct[event['step']]['tool_sha256']
                if repeat==0:
                    old=LazyActivityEdges(f,np.ones(len(f),dtype=bool),len(v))
                    new=CertificateActivityEdges(certificate.quality_view(v,f))
                    directed=np.stack((f,np.roll(f,-1,axis=1)),axis=-1).reshape(-1,2)
                    edges=np.unique(np.sort(directed,axis=1),axis=0)
                    for a,b in edges:
                        edge=int(a),int(b)
                        assert old[edge]==new[edge];edge_queries+=1
                    for a in range(min(len(v),100)):
                        edge=a,a
                        assert (edge in old)==(edge in new)==False;edge_queries+=1
                    bindings.append(dict(budget=route['budget_ms'],step=event['step'],source_sha256=sha(event['source_path']),
                        bits_sha256=sha(Path(event['source_path']).with_name(f"e{event['step']:02d}_source_bits.npy")),all_global_edge_owners_identical=True,queries=len(edges)+min(len(v),100)))
                def run(shared):
                    method=maintain_input if shared else reference.maintain_input
                    start=perf_counter()
                    args=dict(guard_class=NativeLocalGuard,minimum_input_area_mm2=0,max_flips=4)
                    if shared:args['certificate']=certificate
                    state,result=method(v,f,bits,tv.min(0),tv.max(0),1000,**args)
                    return state,result,(perf_counter()-start)*1000
                # 充足预算限定相同最多四次操作，避免把剩余时间不同混入组件机制对照。
                if repeat%2==0:a,ra,ta=run(False);b,rb,tb=run(True)
                else:b,rb,tb=run(True);a,ra,ta=run(False)
                np.testing.assert_array_equal(a.vertices,b.vertices);np.testing.assert_array_equal(a.faces,b.faces)
                np.testing.assert_array_equal(a.bits,b.bits)
                assert ra['operations']==rb['operations'] and ra['visited']==rb['visited'] and ra['rejected']==rb['rejected']
                exact=full.audit(b.vertices,b.faces);assert exact['embedded_closed']
                assert certificate.check_flips(b.vertices,b.faces,rb['operations'])['embedded_closed']
                rows.append(dict(budget=route['budget_ms'],step=event['step'],repeat=repeat,reference=ra,shared=rb,
                    reference_call_ms=ta,shared_call_ms=tb,full_output=exact))
            certificate.close();save()
    # 首个实际源验证逐位绑定；视图在原证书零操作提交、替换、关闭后同样过期。
    event=next(r for r in prior['routes'] if r['budget_ms']==100)['events'][0];v,f=obj(event['source_path'])
    c=SharedVerifiedMesh();rejects('缺少实际父',lambda:c.quality_view(v,f));assert c.check(v,f,True)['embedded_closed']
    changed=v.copy();changed[0,0]=np.nextafter(changed[0,0],np.inf)
    rejects('一ULP坐标变化',lambda:c.quality_view(changed,f))
    changed=f.copy();changed[[0,1]]=changed[[1,0]]
    rejects('有向面位置变化',lambda:c.quality_view(v,changed))
    view=c.quality_view(v,f);edge=tuple(sorted(map(int,f[0,:2])))
    cached=CertificateActivityEdges(view);cached[edge]
    assert c.check_flips(v,f,[])['embedded_closed']
    rejects('同指针提交后缓存过期',lambda:cached[edge])
    view=c.quality_view(v,f);assert c.check(v,f,True)['embedded_closed']
    rejects('父证书替换后过期',lambda:view.owners(edge))
    view=c.quality_view(v,f);c.close();rejects('证书关闭后过期',lambda:view.owners(edge))
    assert len(rows)==96 and len(bindings)==32 and len(negative)==6
    report.update(status='completed',pairs=len(rows),global_edge_queries=edge_queries,all_operations_and_arrays_identical=True,
        all_full_outputs_embedded=True,scope='已见32源三轮同源配对，完整边对拍仅首轮；充足预算最多四操作，不能代替整帧预算评价')
    save()
except Exception as error:
    report.update(status='failed',error=repr(error));save();raise
print(json.dumps(dict(status='completed',pairs=len(rows),queries=edge_queries,negative_controls=len(negative),
    reference_preparation_median_ms=float(np.median([r['reference']['preparation_ms'] for r in rows])),
    shared_preparation_median_ms=float(np.median([r['shared']['preparation_ms'] for r in rows])))),flush=True)
