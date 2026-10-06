"""完整记录全部输入的严格差异与重复性；诊断结束不代表几何等同成立。"""
import argparse
from datetime import datetime,timezone,timedelta
import hashlib,json
from pathlib import Path
import numpy as np
import trimesh
from geogram_memory import GeogramMemory
from exact_mesh_memory import ExactMeshMemory
from verify_geogram_memory import canonical


def read_obj(path):
    # 保留未引用顶点和原始索引，避免输入加载器偷偷改变已有父链。
    vertices=[];faces=[]
    for line in Path(path).read_text().splitlines():
        if line.startswith('v '):vertices.append([float(x) for x in line.split()[1:]])
        elif line.startswith('f '):faces.append([int(x)-1 for x in line.split()[1:]])
    return np.asarray(vertices,dtype=np.float64).reshape(-1,3),np.asarray(faces,dtype=np.int64).reshape(-1,3)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--baseline',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);args=p.parse_args();args.output.mkdir(exist_ok=False)
    sha=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest();api=GeogramMemory();full=ExactMeshMemory();cases=[]
    identity=json.loads(Path(__file__).with_name('build_identity.json').read_text());assert identity['status']=='completed'
    for library in identity['libraries']:assert sha(library['path'])==library['sha256']
    # 实际映射也须来自新私有库，不能因相同SONAME而误用原版已加载依赖。
    mapped=[line for line in Path('/proc/self/maps').read_text().splitlines() if 'libgeogram.so' in line]
    assert any(str(Path(identity['libraries'][0]['path']).resolve()) in line for line in mapped)
    a=trimesh.creation.box(extents=[2]*3)
    for name,size,center,volume in [('不相交',2,[4,0,0],8),('交叉',2,[1,1,1],7),('内腔',1,[0,0,0],7),
        ('完全重合',2,[0,0,0],0),('整面接触',2,[2,0,0],8),('共边接触',2,[2,2,0],8),('共点接触',2,[2,2,2],8)]:
        b=trimesh.creation.box(extents=[size]*3);b.apply_translation(center);cases.append((name,a.copy(),b,volume,None))
    b=trimesh.creation.box(extents=[2]*3);anchor=int(np.argmin(np.asarray(b.vertices).sum(1)))
    b.apply_transform(trimesh.transformations.rotation_matrix(2.6,[1,-1,.1]));b.apply_translation(np.array([1,1,1])-b.vertices[anchor])
    # 明确保存一个逐位共同顶点，同时保留后续跨输入的穿越，不能按共同顶点直接跳过。
    b.vertices[anchor]=[1,1,1];cases.append(('共点且继续穿越',a.copy(),b,None,None))
    inner=trimesh.creation.box(extents=[2]*3);inner.faces=np.asarray(inner.faces)[:,::-1]
    shell=trimesh.util.concatenate([trimesh.creation.box(extents=[4]*3),inner])
    cases.append(('材料内孔不被工具触及',shell,trimesh.creation.box(extents=[.4]*3),56,None))
    b=trimesh.creation.box(extents=[4,1,1]);b.apply_translation([.2,.3,.4]);cases.append(('内外双壳交叉',shell.copy(),b,None,None))
    sphere=trimesh.creation.icosphere(subdivisions=1);b=trimesh.creation.box(extents=[1]*3);b.apply_translation([.8,.1,.2])
    cases.append(('弯曲面交叉',sphere,b,None,None))
    baseline=args.baseline/'trials_02/r0_cpu';record=json.loads((baseline/'01-真实父反馈四预算完整记录.json').read_text())
    route=next(r for r in record['routes'] if r['budget_ms']==200);events=route['events'];assert len(events)==16
    source=json.loads((args.baseline/'inputs/ct_record.json').read_text())['routes'][0]['events']
    for index,event in enumerate(events):
        parent=args.baseline/'inputs/initial.obj' if index==0 else Path(events[index-1]['output_path'])
        tool=Path(source[index]['tool_path']);av,af=read_obj(parent);bv,bf=read_obj(tool)
        expected=event['parent_sha256'];assert sha(parent)==expected and sha(tool)==event['tool_sha256']
        cases.append((f'真实CT同源第{index+1:02d}刀',trimesh.Trimesh(av,af,process=False),trimesh.Trimesh(bv,bf,process=False),None,event))
    rows=[];report=dict(time_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat(),status='running',rows=rows,
        method_sha256=sha(__file__),baseline_record_sha256=sha(baseline/'01-真实父反馈四预算完整记录.json'),
        build_identity=identity,actual_geogram_maps=mapped,
        scope='已见CT的实际同次父和工具；原始CSG可能非法，两路径必须一致；尚非新机制连续发布或实时显示')
    def save():
        target=args.output/'01-已认证双输入候选同源完整对拍.json';temp=target.with_suffix('.tmp')
        temp.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(target)
    report['strict_failures']=[]
    report['diagnostic_only']=True
    save()
    try:
        for index,(name,a,b,volume,event) in enumerate(cases):
            av,af=np.asarray(a.vertices),np.asarray(a.faces);bv,bf=np.asarray(b.vertices),np.asarray(b.faces)
            ac,bc=full.audit(av,af),full.audit(bv,bf);assert ac['embedded_closed'] and bc['embedded_closed']
            directory=args.output/f'case{index:02d}';directory.mkdir();np.savez(directory/'inputs.npz',av=av,af=af,bv=bv,bf=bf)
            expected=None
            if event:
                ev,ef=read_obj(event['raw_path']);eb=np.load(Path(event['raw_path']).with_name(f'e{event["step"]:02d}_raw_bits.npy'));expected=canonical(ev,ef,eb)
            pairs=[];first=None
            for repeat in range(3):
                actual={};timing={};checks={}
                for mode in ([False,True] if repeat%2==0 else [True,False]):
                    v,f,bits,t=api.difference(av,af,bv,bf,no_simplify=True,certified_operands=mode)
                    actual[mode]=canonical(v,f,bits);timing[str(mode)]=t
                    checks[str(mode)]=full.audit(v,f) if len(f) else dict(empty_result=True,faces=0)
                    if repeat==0:np.savez(directory/('certified.npz' if mode else 'original.npz'),vertices=v,faces=f,bits=bits)
                    if volume is not None:assert abs(trimesh.Trimesh(v,f,process=False).volume-volume)<1e-11
                # 保留每项严格失败并继续取证，原严格验证器及其失败记录不改。
                if actual[False]!=actual[True]:
                    report['strict_failures'].append(dict(case=name,repeat=repeat,reason='跨模式集合不同',
                        vertices_identical=actual[False][0]==actual[True][0],
                        original_only_faces=len(set(actual[False][1])-set(actual[True][1])),
                        candidate_only_faces=len(set(actual[True][1])-set(actual[False][1]))))
                if expected is not None and actual[False]!=expected:
                    report['strict_failures'].append(dict(case=name,repeat=repeat,reason='默认模式与原保存集合不同'))
                keys=['topology_valid','closed','embedded_closed','self_intersection_pairs','exact_degenerate_faces'] if len(f) else ['empty_result','faces']
                if not all(checks['False'][k]==checks['True'][k] for k in keys):
                    report['strict_failures'].append(dict(case=name,repeat=repeat,reason='两模式完整检查不同'))
                if first is None:first=actual[False]
                elif first!=actual[False]:
                    report['strict_failures'].append(dict(case=name,repeat=repeat,reason='默认模式跨轮集合不同'))
                pairs.append(dict(repeat=repeat,timings=timing,checks=checks,oriented_sets_identical=actual[False]==actual[True],
                    saved_source_identical=expected is None or actual[False]==expected))
            rows.append(dict(name=name,input_a=ac,input_b=bc,paired_runs=pairs,oriented_sets_identical=all(x['oriented_sets_identical'] for x in pairs),
                original_saved_source_identical=expected is not None and all(x['saved_source_identical'] for x in pairs),input_sha256=sha(directory/'inputs.npz')))
            save();print(json.dumps(dict(case=name,ms={k:t['total_ms'] for k,t in timing.items()},raw_embedded=checks['True'].get('embedded_closed'))),flush=True)
        report['status']='completed_with_differences' if report['strict_failures'] else 'completed';report['cases']=len(rows);report['paired_runs']=len(rows)*3;save()
    except Exception as error:
        report['status']='failed';report['error']=repr(error);save();raise


if __name__=='__main__':main()
