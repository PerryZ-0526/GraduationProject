"""对完整批量反馈的实际保存对象计算有限几何探针，距离不作停止门槛。"""
import hashlib,json,sys
from datetime import datetime,timezone,timedelta
from pathlib import Path
from time import perf_counter
import numpy as np
import trimesh
import pyvista as pv
from vtkmodules.vtkCommonDataModel import vtkStaticCellLocator
from vtkmodules.vtkCommonCore import reference as vtk_reference


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def points(v,f,seed):
    mesh=trimesh.Trimesh(v,f,process=False);rng=np.random.default_rng(seed)
    ids=rng.choice(len(f),512,p=mesh.area_faces/mesh.area);uv=rng.random((512,2));uv[uv.sum(axis=1)>1]=1-uv[uv.sum(axis=1)>1]
    tri=v[f[ids]];sample=tri[:,0]+uv[:,0,None]*(tri[:,1]-tri[:,0])+uv[:,1,None]*(tri[:,2]-tri[:,0])
    # 未引用历史顶点不属于表面，不参与表面距离探针。
    return np.vstack((v[np.unique(f)],sample))


def distances(v,f,query):
    poly=pv.PolyData(v,np.column_stack((np.full(len(f),3),f)).ravel())
    locator=vtkStaticCellLocator();locator.SetDataSet(poly);locator.BuildLocator()
    result=[];closest=[0.0]*3;cid,sid,square=vtk_reference(0),vtk_reference(0),vtk_reference(0.0)
    for point in query:
        locator.FindClosestPoint(point,closest,cid,sid,square);result.append(np.sqrt(float(square)))
    a=np.asarray(result);return dict(count=len(a),max_mm=float(a.max()),p95_mm=float(np.percentile(a,95)),rms_mm=float(np.sqrt(np.mean(a*a))))


def main():
    root=Path(sys.argv[1]);path=root/'03-完整批量父反馈记录.json';report=json.loads(path.read_text(encoding='utf-8'))
    assert report['status'] in ('completed','completed_with_recorded_failures') and report['mode']=='long'
    full_path=root/'04-实际保存数组完整精确复审.json';full=json.loads(full_path.read_text(encoding='utf-8'))
    assert full['status']=='completed' and full['parent_chain_passed'];checks={(item['run'],item['update'],item['kind']):item for item in full['arrays']}
    started=perf_counter();rows=[]
    for run in report['runs']:
        if not run['label'].endswith('_candidate'):continue
        reference=next(item for item in report['runs'] if item['label']==run['label'].replace('_candidate','_reference'))
        other={row['update']:row for row in reference['rows'] if row['status']=='published_verified'}
        for row in run['rows']:
            update=row['update']
            if row['status']!='published_verified' or update not in other:continue
            assert row['tool_sha256']==other[update]['tool_sha256'] and row['event_steps']==other[update]['event_steps']
            pair=[]
            for branch in (run,reference):
                saved=checks[branch['label'],update,'output'];output=root/saved['path']
                assert saved['check']['embedded_closed'] and sha(output)==saved['file_sha256']
                with np.load(output) as data:pair.append((data['vertices'].copy(),data['faces'].copy()))
            (cv,cf),(rv,rf)=pair
            rows.append(dict(route=run['label'],update=update,event_steps=row['event_steps'],
                candidate_to_reference=distances(rv,rf,points(cv,cf,20261007+update)),
                reference_to_candidate=distances(cv,cf,points(rv,rf,20261007+update)),
                candidate_file_sha256=checks[run['label'],update,'output']['file_sha256'],
                reference_file_sha256=checks[reference['label'],update,'output']['file_sha256']))
    output=dict(time_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat(),status='completed',worker_sha256=sha(__file__),
        report_sha256=sha(path),full_audit_sha256=sha(full_path),rows=rows,elapsed_ms=(perf_counter()-started)*1000,
        geometry_policy='report_only_no_distance_stop',scope='两种批反馈共享CSG与必要修复，关闭可选质量为参照；有限表面探针，不是独立真值或最坏距离证书')
    target=root/'07-同次批材料参照有限几何探针.json';temporary=target.with_suffix('.tmp')
    temporary.write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8');temporary.replace(target)
    print(json.dumps(dict(paired_updates=len(rows),elapsed_ms=output['elapsed_ms'],max_mm=max((item[key]['max_mm'] for item in rows for key in ('candidate_to_reference','reference_to_candidate')),default=None))),flush=True)


if __name__=='__main__':main()
