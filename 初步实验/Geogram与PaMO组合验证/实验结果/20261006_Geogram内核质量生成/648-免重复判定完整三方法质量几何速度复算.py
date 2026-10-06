"""复算全部336实际对象，再报告16同输入三方法完整耗时分布。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import ast
import hashlib
import io
import json
import zipfile
import numpy as np
import trimesh
import pyvista as pv
import vtk

here=Path(__file__).resolve().parent
archive_path=here/'647-免重复判定三方法完整336计划归档.zip'
z=zipfile.ZipFile(archive_path);assert z.testzip() is None
raw=z.read('01-免重复判定十六已见三方法实际记录.json');record=json.loads(raw)
assert record['status']=='completed_all_336_seen_input_three_method_attempts' and len(record['rows'])==record['planned_calls']==336
plan=here/'644-免重复判定十六已见三方法执行计划.json'
assert record['plan_sha256']==hashlib.sha256(plan.read_bytes()).hexdigest()
manifest=json.loads((here/'574-新边拒绝固定方法第二批十六新参数运行前冻结清单.json').read_text('utf8'))
original_trimesh=trimesh
class ZipMesh:
    """读取原归档中的保存网格，输入绝对路径仍从本机核对。"""
    def load(self,path,**kwargs):
        path=Path(path)
        if path.is_absolute():return original_trimesh.load(path,**kwargs)
        return original_trimesh.load(io.BytesIO(z.read(path.as_posix())),file_type='obj',**kwargs)
trimesh=ZipMesh()
def functions(path,names):
    """只加载既有复算函数，避免运行其历史远程入口。"""
    tree=ast.parse(path.read_text('utf8'));nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
    scope={'np':np,'trimesh':trimesh,'pv':pv,'vtk':vtk}
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),scope);return scope
quality=functions(here/'04-原版生成阶段同输入基线.py',{'quality'})['quality']
utils=functions(here/'397-共面前清理十四输入全部质量几何速度复算.py',{'distances','timing'})
now=lambda:datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
output=here/'649-免重复判定十六已见三方法完整统计.json';assert not output.exists()
summary={'生成时间':now(),'修改时间及修改内容':'首次336实际调用三方法完整独立复算','文档概述':'逐保存对象摘要及精确检查、完整质量范围、六次速度分布和有限几何抽样；输入已见只作开发回归',
    '索引目录':['cases','rows','totals'],'status':'running','archive_sha256':hashlib.sha256(archive_path.read_bytes()).hexdigest(),
    'source_record_sha256':hashlib.sha256(raw).hexdigest(),'cases':[],'rows':[],'preflight':[]}
def save():
    """逐输入写真实已完成证据，未终态不记完成。"""
    output.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n','utf8')
for p in record['preflight']:
    data=z.read(Path(p['audit']['path']).name);assert hashlib.sha256(data).hexdigest()==p['audit']['sha256']
    actual=json.loads(data);assert actual['returncode']==0 and json.loads(actual['stdout'])['embedded_closed']
    summary['preflight'].append(p)
assert len(summary['preflight'])==32
save()
for i,case in enumerate(manifest['cases']):
    current={'index':i,'case':case['id'],'kind':case['kind'],'methods':{},'geometry':{}}
    first={}
    for method in ['baseline','previous','candidate']:
        rows=[r for r in record['rows'] if r['case_index']==i and r['method']==method]
        assert len(rows)==7 and sorted(r['repeat'] for r in rows)==[-1,0,1,2,3,4,5]
        qualities=[];valid=0
        for r in rows:
            item=dict(r)
            if r['returncode']==0:
                path=Path(f'{i:02d}')/Path(r['mesh_path']).name
                assert hashlib.sha256(z.read(path.as_posix())).hexdigest()==r['mesh_sha256']
                ap=Path(f'{i:02d}')/Path(r['audit']['path']).name;data=z.read(ap.as_posix())
                assert hashlib.sha256(data).hexdigest()==r['audit']['sha256']
                wrapped=json.loads(data);actual=json.loads(wrapped['stdout']) if wrapped['returncode']==0 else None
                good=bool(actual and actual['embedded_closed']);assert good==r['audit']['embedded_closed']
                item.update(quality=quality(path),exact_audit=actual);valid+=good
                if r['repeat']>=0:qualities.append(item['quality'])
                if r['repeat']==0:first[method]=path
            summary['rows'].append(item)
        measured=[r for r in rows if r['repeat']>=0 and r['returncode']==0]
        current['methods'][method]={'planned_calls':7,'returned_calls':sum(r['returncode']==0 for r in rows),'exact_valid_calls':valid,
            'boolean_timing':utils['timing']([r['native_timing']['boolean_ms'] for r in measured]) if measured else None,
            'process_timing_all_measured':utils['timing']([r['subprocess_wall_ms'] for r in rows if r['repeat']>=0]),
            'first_quality':next((r['quality'] for r in summary['rows'] if r['case_index']==i and r['method']==method and r['repeat']==0 and 'quality' in r),None),
            'measured_quality_ranges':{k:{'min':min(q[k] for q in qualities),'max':max(q[k] for q in qualities)} for k in ['faces','below_10_faces','below_10_area_mm2','nonpositive_or_nonfinite_faces']} if qualities else None}
    for label,a,b in [('baseline_to_candidate','baseline','candidate'),('candidate_to_baseline','candidate','baseline'),('previous_to_candidate','previous','candidate'),('candidate_to_previous','candidate','previous')]:
        if a in first and b in first:current['geometry'][label]=utils['distances'](first[a],first[b],2026100700+i)
    if all(current['methods'][m]['boolean_timing'] for m in ['baseline','previous','candidate']):
        current['candidate_previous_median_ratio']=current['methods']['candidate']['boolean_timing']['median_ms']/current['methods']['previous']['boolean_timing']['median_ms']
        current['candidate_baseline_median_ratio']=current['methods']['candidate']['boolean_timing']['median_ms']/current['methods']['baseline']['boolean_timing']['median_ms']
    summary['cases'].append(current);save()
    print(i,current.get('candidate_previous_median_ratio'),current.get('candidate_baseline_median_ratio'),current['methods']['candidate']['exact_valid_calls'],flush=True)
summary.update(status='completed_all_336_saved_native_calls_quality_geometry_timing_recomputed',finished_beijing=now(),
    totals={m:{'planned':112,'returned':sum(r['method']==m and r['returncode']==0 for r in summary['rows']),
        'exact_valid':sum(r['method']==m and bool(r.get('exact_audit',{}).get('embedded_closed')) for r in summary['rows'])} for m in ['baseline','previous','candidate']})
save();assert len(summary['rows'])==336 and len(summary['cases'])==16
print(json.dumps(summary['totals'],ensure_ascii=False))
