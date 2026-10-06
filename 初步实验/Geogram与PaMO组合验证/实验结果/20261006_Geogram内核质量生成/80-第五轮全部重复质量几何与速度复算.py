"""对全部实际重复网格独立复算质量，再比较首份同源几何和原生计时分布。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import ast
import hashlib
import json
import numpy as np
import trimesh
import pyvista as pv
import vtk

here=Path(__file__).resolve().parent
folder=here/'第五轮原生全部重复与诊断输出'
record_path=folder/'01-原生十一同输入交错质量速度记录.json'
record=json.loads(record_path.read_text('utf8'))
assert record['status']=='completed_all_native_paired_development_runs'
manifest_path=here/'18-原生十一同输入开发与速度运行前清单.json'
manifest=json.loads(manifest_path.read_text('utf8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert record['input_manifest_sha256']==sha(manifest_path)
# 仅加载独立角度复算函数，不能导入带远程执行副作用的入口。
detector_path=here/'04-原版生成阶段同输入基线.py'
module=ast.parse(detector_path.read_text('utf8'))
function=next(n for n in module.body if isinstance(n,ast.FunctionDef) and n.name=='quality')
scope={'np':np,'trimesh':trimesh}
exec(compile(ast.Module(body=[function],type_ignores=[]),str(detector_path),'exec'),scope)
quality=scope['quality']


def distances(source,target,seed):
    """双向各八千余面积样本及全部源顶点；结果为抽样分布。"""
    a=trimesh.load(source,process=False,force='mesh')
    b=trimesh.load(target,process=False,force='mesh')
    faces=np.column_stack([np.full(len(b.faces),3),b.faces]).reshape(-1)
    poly=pv.PolyData(np.asarray(b.vertices),faces)
    locator=vtk.vtkStaticCellLocator(); locator.SetDataSet(poly); locator.BuildLocator()
    rng=np.random.default_rng(seed)
    tris=np.asarray(a.vertices)[np.asarray(a.faces)]
    areas=np.linalg.norm(np.cross(tris[:,1]-tris[:,0],tris[:,2]-tris[:,0]),axis=1)/2
    chosen=rng.choice(len(tris),8192,p=areas/areas.sum())
    u=np.sqrt(rng.random(8192));v=rng.random(8192)
    samples=(1-u[:,None])*tris[chosen,0]+(u*(1-v))[:,None]*tris[chosen,1]+(u*v)[:,None]*tris[chosen,2]
    def query(points):
        values=[]
        cell_id=vtk.mutable(0); sub_id=vtk.mutable(0); squared=vtk.mutable(0.0); closest=[0.0]*3
        for point in points:
            locator.FindClosestPoint(point,closest,cell_id,sub_id,squared)
            values.append(float(squared)**0.5)
        return np.asarray(values)
    area=query(samples);vertices=query(np.asarray(a.vertices))
    return {'area_max_mm':float(area.max()),'all_vertices_max_mm':float(vertices.max()),
            'area_quantiles_mm':{str(q):float(np.quantile(area,q)) for q in [.5,.9,.95,.99,1]},
            'area_within_distance_fraction':{str(t):float((area<=t).mean()) for t in [.01,.05,.1,.15,.2]}}


def timing(values):
    """报告全部六次计时的范围及分位数，不挑最快一次。"""
    a=np.asarray(values)
    return {'min_ms':float(a.min()),'median_ms':float(np.median(a)),
            'p95_ms':float(np.quantile(a,.95)),'max_ms':float(a.max()),'repeats':len(a)}


summary={'生成时间':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),
         '修改时间及修改内容':'首次对全部实际重复质量及同源几何完整复算',
         '文档概述':'原生内部质量生成开发；首份静态准确检查与重复质量分别列明',
         '索引目录':['cases','all_repeat_quality'],'status':'running',
         'source_record_sha256':sha(record_path),'detector_sha256':sha(detector_path),'auditor_sha256':sha(Path(__file__)),
         'cases':[],'all_repeat_quality':[]}
output=here/'81-第五轮原生十一同输入质量几何与速度复算.json'
assert not output.exists()


def save():
    """逐案例保存已完成的证据，未结束不能视为整体通过。"""
    output.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n','utf8')


save()
for i,case in enumerate(manifest['cases']):
    row={'case':case['id'],'index':i,'input_parent_quality':quality(Path(case['parent'])),
         'parent_sha256':case['parent_sha256'],'tool_sha256':case['tool_sha256'],'methods':{}}
    first={}
    for method in ['baseline','candidate']:
        runs=[r for r in record['rows'] if r['case_index']==i and r['method']==method]
        assert len(runs)==7 and all(r['returncode']==0 for r in runs)
        qualities=[]
        for run in runs:
            path=folder/f'{i:02d}'/Path(run['mesh_path']).name
            assert sha(path)==run['mesh_sha256']
            q=quality(path)
            assert q['faces']==run['native_timing']['faces']
            summary['all_repeat_quality'].append({'case_index':i,'method':method,'repeat':run['repeat'],
                'mesh_sha256':sha(path),'quality':q})
            if run['repeat']>=0: qualities.append(q)
            if run['repeat']==0: first[method]=path
        # 并行输出顺序可能引起浮点求和差异，完整报告重复范围，不要求日志逐值相等。
        repeat_ranges={key:{'min':min(q[key] for q in qualities),'max':max(q[key] for q in qualities)}
                       for key in ['faces','below_10_faces','below_10_area_mm2','volume_mm3','nonpositive_or_nonfinite_faces']}
        audited=next(a for a in record['native_audits'] if a['case_index']==i and a['method']==method)
        ap=folder/f'{i:02d}'/Path(audited['audit_path']).name
        assert sha(ap)==audited['audit_sha256'] and sha(first[method])==audited['mesh_sha256']
        audit=json.loads(ap.read_text('utf8'))
        native=json.loads(audit['stdout']) if audit['returncode']==0 else None
        row['methods'][method]={'quality':qualities[0],'repeat_quality_ranges':repeat_ranges,'native_first_output_audit':audit,
                               'first_output_embedded_closed':bool(native and native['embedded_closed']),
                               'boolean_timing':timing([r['native_timing']['boolean_ms'] for r in runs if r['repeat']>=0]),
                               'process_timing':timing([r['subprocess_wall_ms'] for r in runs if r['repeat']>=0])}
    row['geometry']={'baseline_to_candidate':distances(first['baseline'],first['candidate'],2026100600+i),
                     'candidate_to_baseline':distances(first['candidate'],first['baseline'],2026100700+i)}
    b,c=[row['methods'][m]['quality'] for m in ['baseline','candidate']]
    row['bad_count_change']=c['below_10_faces']-b['below_10_faces']
    row['bad_area_change_mm2']=c['below_10_area_mm2']-b['below_10_area_mm2']
    row['boolean_median_ratio']=row['methods']['candidate']['boolean_timing']['median_ms']/row['methods']['baseline']['boolean_timing']['median_ms']
    summary['cases'].append(row);save()
    print(case['id'],b['below_10_faces'],'->',c['below_10_faces'],
          '面积',round(row['bad_area_change_mm2'],9),'耗时倍率',round(row['boolean_median_ratio'],3),flush=True)
summary.update(status='completed_all_154_saved_quality_recomputations_and_eleven_geometry_timing_pairs',
               finished_beijing=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'))
assert len(summary['all_repeat_quality'])==154 and len(summary['cases'])==11
save()
