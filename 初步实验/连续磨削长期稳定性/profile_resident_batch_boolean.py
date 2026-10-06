"""同一保存父网格上比较逐刀更新与多工具一次差集，完整认证后才反馈。"""
from datetime import datetime,timezone,timedelta
import hashlib,json,shutil,subprocess,sys
from pathlib import Path
from time import perf_counter
import numpy as np
import trimesh
import pyvista as pv
from vtkmodules.vtkCommonDataModel import vtkStaticCellLocator
from vtkmodules.vtkCommonCore import reference as vtk_reference


def now():return datetime.now(timezone(timedelta(hours=8))).isoformat()


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    base,root=map(Path,sys.argv[1:3]);root.mkdir(exist_ok=False)
    assert json.loads((base/'02-常驻长序列完整记录.json').read_text())['status']=='completed_with_recorded_failures'
    workers=root/'workers';shutil.copytree(base/'workers',workers)
    # 旧修复器把来源编码限制为两操作数；这里只扩大编码域，逐标签守卫与原始位掩码保持。
    for name in ['short_edge_repair.py','covered_zero_cleanup.py']:
        target=workers/name;text=target.read_text();anchor='np.any(~np.isin(labels,[1,2,3]))'
        assert text.count(anchor)==1
        text=text.replace(anchor,'np.any(labels<=0)')
        target.write_text(text)
    for name in ['geogram_batch_memory.cpp','geogram_batch_memory.py']:
        shutil.copyfile(Path(__file__).with_name(name),workers/name)
    identity_path=workers/'build_identity.json';identity=json.loads(identity_path.read_text())
    for row in identity['libraries']:assert sha(row['path'])==row['sha256']
    geogram=Path('/tmp/geogram_certified_pairs_20261006_r3')
    argv=['g++','-std=c++17','-O3','-DNDEBUG','-shared','-fPIC','-DGEO_DYNAMIC_LIBS','-DGEOGRAM_USE_BUILTIN_DEPS',
        '-fno-fast-math','-ffp-contract=off','-frounding-math','-I'+str(geogram/'geogram_source/src/lib'),
        str(workers/'geogram_batch_memory.cpp'),str(geogram/'geogram_build/lib/libgeogram.so'),
        '-Wl,-rpath,'+str(geogram/'geogram_build/lib'),'-o',str(workers/'libgeogram_memory.so')]
    build=subprocess.run(argv,capture_output=True,text=True)
    (root/'01-多工具入口编译日志.txt').write_text(build.stdout+build.stderr)
    if build.returncode:raise RuntimeError('多工具内存入口编译失败')
    for row in identity['libraries']:
        if Path(row['path']).name=='libgeogram_memory.so':row.update(path=str(workers/'libgeogram_memory.so'),sha256=sha(workers/'libgeogram_memory.so'))
    identity['batch_entry_compile_argv']=argv;identity_path.write_text(json.dumps(identity,ensure_ascii=False,indent=2))
    sys.path.insert(0,str(workers));sys.path.insert(0,str(base))
    from geogram_batch_memory import GeogramBatchMemory
    from incremental_mesh_memory import VerifiedMesh
    from exact_mesh_memory import ExactMeshMemory
    from numeric_input import check_and_boxes
    from covered_zero_cleanup import clean_arrays
    from short_edge_repair import repair_short_edges
    from native_guard import separated_native
    from resident_source_cleanup import cancel_opposed_index_faces,repair_short_edge_clusters
    from benchmark import quality
    api=GeogramBatchMemory();full=ExactMeshMemory();manifest=json.loads((base/'manifest.json').read_text())
    record=dict(time_beijing=now(),status='running',base=str(base),worker_sha256=sha(__file__),build_argv=argv,
        sources={p.name:sha(p) for p in workers.iterdir() if p.suffix in ['.py','.cpp','.so','.json']},cases=[],
        scope='已见保存父网格的批量组件；原全部工具保持，无可选质量操作；不等于端到端实时或连续384事件完成')
    path=root/'02-批量布尔同父输入完整对照.json'
    def save():
        temp=path.with_suffix('.tmp');temp.write_text(json.dumps(record,ensure_ascii=False,indent=2));temp.replace(path)
    def prepare(v,f,bits,parent,certificate,tool_count):
        start=perf_counter();invalid,_,_=check_and_boxes(v,f,0);cleanup=None;cluster=None
        # 位掩码还必须落在本次真实操作数范围；不合并工具标签，也不截断高位来源。
        if np.any(bits<=0) or np.any(bits>((1<<(tool_count+1))-1)):raise ValueError('来源位超出本批真实操作数范围')
        if invalid:v,f,bits,cleanup=clean_arrays(v,f,bits)
        remaining=200-(perf_counter()-start)*1000
        # 与v10必要修复一致：原预算、自然收缩上限、父锚点与全部分离守卫保持。
        v,f,bits,repair=repair_short_edges(v,f,bits,parent,max(0,remaining-50),max_collapses=len(f)//2,separation_check=separated_native)
        v,f,bits,opposed=cancel_opposed_index_faces(v,f,bits)
        invalid,_,_=check_and_boxes(v,f,0)
        if invalid and not np.isfinite(v).all():raise ValueError('多工具输出仍非有限')
        check=dict(embedded_closed=False,advanced=False,numeric_invalid_source=True) if invalid else certificate.check(v,f,advance=True)
        if not check['embedded_closed']:
            nv,nf,nb,cluster=repair_short_edge_clusters(v,f,bits,parent,tolerance_mm=5e-9)
            cluster['original_failed_check']=check
            if cluster['candidate']:
                candidate_check=certificate.check(nv,nf,advance=True);cluster['candidate_check']=candidate_check
                if candidate_check['embedded_closed']:v,f,bits,check=nv,nf,nb,candidate_check
        return v,f,bits,dict(accepted=check['embedded_closed'],check=check,cleanup=cleanup,repair=repair,
            opposed=opposed,cluster=cluster,elapsed_ms=(perf_counter()-start)*1000)
    def execute(v,f,tools,method,folder):
        folder.mkdir();certificate=VerifiedMesh();assert certificate.check(v,f,advance=True)['embedded_closed']
        steps=[];processed=0;start=perf_counter();accepted=False
        try:
            for index,group in enumerate([tools] if method=='batch' else [[tool] for tool in tools]):
                parent=v
                if method=='batch':rv,rf,bits,boolean=api.difference_batch(v,f,group,certified_operands=True)
                else:rv,rf,bits,boolean=api.difference(v,f,*group[0],no_simplify=True,certified_operands=True)
                raw_bits=bits.copy()
                v,f,bits,repair=prepare(rv,rf,bits,parent,certificate,len(group));processed+=len(group);accepted=repair['accepted']
                steps.append(dict(update=index,consumed_tools=len(group),boolean=boolean,preparation=repair,
                    raw=(rv,rf,raw_bits),source=(v,f,bits)))
                if not accepted:break
            elapsed=(perf_counter()-start)*1000
        finally:certificate.close()
        # 保存和全量复审在服务计时后；未认证的中间源不进入下一次布尔。
        rows=[]
        for item in steps:
            rv,rf,raw_bits=item.pop('raw');v,f,bits=item.pop('source')
            raw_path=folder/f'e{item["update"]:02d}_raw.npz';source_path=folder/f'e{item["update"]:02d}_source.npz'
            np.savez_compressed(raw_path,vertices=rv,faces=rf,bits=raw_bits)
            np.savez_compressed(source_path,vertices=v,faces=f,bits=bits)
            full_check=full.audit(v,f)
            if item['preparation']['accepted'] and not full_check['embedded_closed']:raise ValueError('已反馈源完整复审失败')
            item.update(full=full_check,raw_sha256=sha(raw_path),source_sha256=sha(source_path));rows.append(item)
        return v,f,dict(accepted=accepted and processed==len(tools),attempted_tools=processed,
            published_tools=sum(item['consumed_tools'] for item in steps if item['preparation']['accepted']),planned_tools=len(tools),
            update_count=len(steps),service_ms=elapsed,final_quality=quality(v,f,0),steps=rows)
    def probes(v,f,seed):
        # 几何探针仅取实际表面引用点加面积样本，未引用的历史顶点不冒充表面。
        mesh=trimesh.Trimesh(v,f,process=False);rng=np.random.default_rng(seed)
        ids=rng.choice(len(f),512,p=mesh.area_faces/mesh.area);uv=rng.random((512,2));uv[uv.sum(axis=1)>1]=1-uv[uv.sum(axis=1)>1]
        triangles=v[f[ids]];samples=triangles[:,0]+uv[:,0,None]*(triangles[:,1]-triangles[:,0])+uv[:,1,None]*(triangles[:,2]-triangles[:,0])
        return np.vstack((v[np.unique(f)],samples))
    def distances(v,f,points):
        poly=pv.PolyData(v,np.column_stack((np.full(len(f),3),f)).ravel())
        locator=vtkStaticCellLocator();locator.SetDataSet(poly);locator.BuildLocator()
        result=[];closest=[0.0]*3;cid,sid,square=vtk_reference(0),vtk_reference(0),vtk_reference(0.0)
        for point in points:
            locator.FindClosestPoint(point,closest,cid,sid,square);result.append(np.sqrt(float(square)))
        a=np.array(result);return dict(count=len(a),max_mm=float(a.max()),p95_mm=float(np.percentile(a,95)),rms_mm=float(np.sqrt(np.mean(a*a))))
    save()
    for route in manifest['routes']:
        body=route['body'];starts=[0,80] if body=='slab' else [0,180]
        for start in starts:
            if start:
                parent_file=base/(route['id']+'_candidate')/f'e{start-1:03d}_output.npz'
                saved=json.loads((parent_file.parent/'03-保存数组清单.json').read_text())
                expected=next(item['sha256'] for item in saved if item['step']==start-1 and item['kind']=='output');assert sha(parent_file)==expected
                with np.load(parent_file) as data:iv,iff=data['vertices'].copy(),data['faces'].copy()
            else:
                parent_file=base/'inputs'/route['initial_mesh'];assert sha(parent_file)==route['initial_mesh_sha256']
                mesh=trimesh.load(parent_file,process=False);iv,iff=np.asarray(mesh.vertices),np.asarray(mesh.faces)
            assert full.audit(iv,iff)['embedded_closed']
            counts=[1,2,5,10] if start==0 else [2,5,10]
            for count in counts:
                folder=root/f'{body}_{start:03d}_{count:02d}';folder.mkdir()
                np.savez_compressed(folder/'parent.npz',vertices=iv,faces=iff)
                tools=[];bindings=[]
                for entry in route['prefix_tools'][start:start+count]:
                    tool_path=base/'inputs'/entry['mesh'];assert sha(tool_path)==entry['sha256']
                    mesh=trimesh.load(tool_path,process=False);tv,tf=np.asarray(mesh.vertices),np.asarray(mesh.faces)
                    check=full.audit(tv,tf);assert check['embedded_closed'];tools.append((tv,tf))
                    shutil.copyfile(tool_path,folder/f'tool{len(tools):02d}.obj');bindings.append(dict(event_id=entry['event_id'],sha256=entry['sha256'],check=check))
                assert len(tools)==count
                case=dict(body=body,start_event=start+1,tool_count=count,parent_sha256=sha(parent_file),original_tools=bindings,trials=[])
                record['cases'].append(case);save()
                for repeat in range(3):
                    pair={};outputs={}
                    for method in (['sequential','batch'] if repeat%2==0 else ['batch','sequential']):
                        v,f,detail=execute(iv.copy(),iff.copy(),tools,method,folder/f'r{repeat}_{method}')
                        pair[method]=detail
                        outputs[method]=(v,f)
                    geometry=None
                    if all(item['accepted'] for item in pair.values()):
                        sv,sf=outputs['sequential'];bv,bf=outputs['batch']
                        geometry=dict(sequential_to_batch=distances(bv,bf,probes(sv,sf,20261007+start)),
                            batch_to_sequential=distances(sv,sf,probes(bv,bf,20261007+start)),
                            scope='同父同工具两种必要修复链的有限表面探针；非算法独立真值，距离只统计')
                    case['trials'].append(dict(repeat=repeat,methods=pair,geometry=geometry));save()
                    print(json.dumps(dict(body=body,start=start+1,count=count,repeat=repeat,
                        sequential_ms=pair['sequential']['service_ms'],batch_ms=pair['batch']['service_ms'],
                        accepted={k:v['accepted'] for k,v in pair.items()},time_beijing=now())),flush=True)
    record.update(status='completed',finished_beijing=now());save()


if __name__=='__main__':
    try:main()
    except Exception as error:
        # 实际进程异常必须单列终止，不让running快照被误当作仍在计算。
        root=Path(sys.argv[2]);target=root/'02-批量布尔同父输入完整对照.json'
        if target.exists():
            record=json.loads(target.read_text());record.update(status='failed',error=repr(error),finished_beijing=now())
            target.write_text(json.dumps(record,ensure_ascii=False,indent=2))
        raise
