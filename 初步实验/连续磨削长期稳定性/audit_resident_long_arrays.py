"""在常驻更新结束后，复审所有保存数组、父链、质量分布及独立参照有限探针。"""
from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
import sys
from time import perf_counter
import numpy as np
import trimesh
import pyvista as pv
from vtkmodules.vtkCommonDataModel import vtkStaticCellLocator
from vtkmodules.vtkCommonCore import reference as vtk_reference


ROOT = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(ROOT / 'workers'))
from exact_mesh_memory import ExactMeshMemory
from benchmark import quality


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def now():
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


def write(path,value):
    temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8');temporary.replace(path)


def points(mesh,seed):
    rng=np.random.default_rng(seed)
    ids=rng.choice(len(mesh.faces),256,p=mesh.area_faces/mesh.area)
    uv=rng.random((256,2));flip=uv.sum(1)>1;uv[flip]=1-uv[flip]
    triangles=mesh.triangles[ids]
    samples=triangles[:,0]+uv[:,0,None]*(triangles[:,1]-triangles[:,0])+uv[:,1,None]*(triangles[:,2]-triangles[:,0])
    # 所有顶点与固定种子的面积采样都保留；这仍是有限探针，不是连续最坏距离证明。
    return np.vstack((mesh.vertices,samples))


def distance(mesh,queries):
    # 使用项目已用于离线几何审计的VTK最近三角面查询，不依赖缺失的rtree。
    poly=pv.PolyData(mesh.vertices,np.column_stack((np.full(len(mesh.faces),3),mesh.faces)).ravel())
    locator=vtkStaticCellLocator();locator.SetDataSet(poly);locator.BuildLocator()
    closest,cid,sid,square=[0.0]*3,vtk_reference(0),vtk_reference(0),vtk_reference(0.0)
    result=np.empty(len(queries))
    for i,point in enumerate(queries):
        locator.FindClosestPoint(point,closest,cid,sid,square);result[i]=np.sqrt(float(square))
    return result


report=json.loads((ROOT/'02-常驻长序列完整记录.json').read_text())
if report['status'] not in ('completed','completed_with_recorded_failures'):raise ValueError('批次尚未终态')
for name in ('04-保存对象完整精确复审.json','05-独立材料参照逐帧有限探针.json'):
    prior=ROOT/name
    if prior.exists():
        # 失败或旧复审快照保留，新的完整复审不会抹去原时间点证据。
        stamp=datetime.now(timezone(timedelta(hours=8))).strftime('%Y%m%d_%H%M%S')
        (ROOT/(prior.stem+'-此前快照-'+stamp+'.json')).write_bytes(prior.read_bytes())
manifest=json.loads((ROOT/'manifest.json').read_text())
full=ExactMeshMemory();audits=[];comparisons=[];failed_checks=[]
started=perf_counter()
for run in report['runs']:
    folder=Path(run['output']);ledger=json.loads((folder/'01-真实父反馈四预算完整记录.json').read_text())
    saved=json.loads((folder/'03-保存数组清单.json').read_text());last_parent=ledger['initial_sha256']
    items={}
    for entry in saved:
        path=Path(entry['path'])
        if sha(path)!=entry['sha256']:raise ValueError('保存数组摘要变化')
        items[(entry['step'],entry['kind'])]=entry
    for event in ledger['routes'][0]['events']:
        step=event['step'];published=event['status']=='published_verified'
        if event.get('parent_sha256') and event['parent_sha256']!=last_parent:raise ValueError('实际父数组链不一致')
        checks={};data={}
        for kind in ('raw','source','output'):
            entry=items.get((step,kind))
            if entry is None:continue
            with np.load(entry['path']) as snapshot:
                v,f,bits=[snapshot[key].copy() for key in ('vertices','faces','bits')]
            check=full.audit(v,f);checks[kind]=check;data[kind]=(v,f,bits)
            if kind in ('source','output') and published and not check['embedded_closed']:
                failed_checks.append(dict(run=run['route'],reference=run['reference'],step=step,kind=kind,check=check))
        if published:
            if 'output' not in data or 'source' not in data:raise ValueError('实际发布数组缺失')
            h=hashlib.sha256()
            for array in data['output']:h.update(memoryview(np.ascontiguousarray(array)).cast('B'))
            if h.hexdigest()!=event['output_array_sha256']:raise ValueError('保存对象与实际交付数组不一致')
            last_parent=h.hexdigest()
        audits.append(dict(route=run['route'],reference=run['reference'],step=step,status=event['status'],checks=checks,
            source_quality=quality(data['source'][0],data['source'][1],0) if 'source' in data else None,
            output_quality=quality(data['output'][0],data['output'][1],0) if 'output' in data else None,
            quality_vertices_bitwise_fixed=bool(np.array_equal(data['source'][0],data['output'][0])) if published else None))
    print(json.dumps(dict(audited_run=run['route'],reference=run['reference'],saved_arrays=len(saved),failed_published=len(failed_checks))),flush=True)
    write(ROOT/'04-保存对象完整精确复审.json',dict(time_beijing=now(),status='running',audits=audits,failed_published_checks=failed_checks))
for route in manifest['routes']:
    candidate=ROOT/(route['id']+'_candidate');reference=ROOT/(route['id']+'_reference')
    initial=trimesh.load(ROOT/'inputs'/route['initial_mesh'],process=False)
    outside=np.ones(len(initial.vertices),dtype=bool)
    for step,tool in enumerate(route['prefix_tools']):
        mesh=trimesh.load(ROOT/'inputs'/tool['mesh'],process=False)
        outside &= ~np.all((initial.vertices>=mesh.bounds[0])&(initial.vertices<=mesh.bounds[1]),axis=1)
        cp=candidate/f'e{step:03d}_output.npz';rp=reference/f'e{step:03d}_output.npz'
        if not cp.exists() or not rp.exists():continue
        with np.load(cp) as c,np.load(rp) as r:
            cm=trimesh.Trimesh(c['vertices'],c['faces'],process=False);rm=trimesh.Trimesh(r['vertices'],r['faces'],process=False)
        forward=distance(rm,points(cm,20261006+step))
        reverse=distance(cm,points(rm,20261006+step))
        exterior=distance(cm,initial.vertices[outside]) if outside.any() else np.array([])
        stats=lambda d:dict(count=len(d),max_mm=float(d.max()),p95_mm=float(np.percentile(d,95)),rms_mm=float(np.sqrt(np.mean(d*d))))
        comparisons.append(dict(route=route['id'],step=step,forward=stats(forward),reverse=stats(reverse),
            probe_max_mm=max(float(forward.max()),float(reverse.max())),
            outside_original_tool_aabbs=stats(exterior) if len(exterior) else None))
        if (step+1)%24==0:
            print(json.dumps(dict(geometry_route=route['id'],step=step+1,probe_max_mm=comparisons[-1]['probe_max_mm'])),flush=True)
            write(ROOT/'05-独立材料参照逐帧有限探针.json',dict(time_beijing=now(),status='running',comparisons=comparisons))
write(ROOT/'04-保存对象完整精确复审.json',dict(time_beijing=now(),status='completed',audits=audits,
    failed_published_checks=failed_checks,parent_chains_checked=True,execution_record_sha256=sha(ROOT/'02-常驻长序列完整记录.json')))
write(ROOT/'05-独立材料参照逐帧有限探针.json',dict(time_beijing=now(),status='completed',comparisons=comparisons,
    geometry_policy='仅统计，不因距离大小拒绝或停止',sample_scope='每方向全部顶点加256面积采样；外部点限累计原工具AABB外初态顶点',
    reference_scope='独立从初态的无可选翻边材料链，共享布尔及必要修复，不称独立算法真值',audit_wall_ms=(perf_counter()-started)*1000))
if failed_checks:raise ValueError('实际发布对象完整复审失败')
