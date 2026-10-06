"""完整224计划分母复算，返回失败、保存几何失败和成功计时分别报告。"""
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
folder=here/'固定方法十六新参数全部实际输出'
record_path=folder/'01-固定方法十六新参数交错质量速度记录.json'
record=json.loads(record_path.read_text('utf8'))
manifest_path=here/'442-固定方法新参数十六输入运行前冻结清单.json'
manifest=json.loads(manifest_path.read_text('utf8'))
method_path=here/'440-固定原生主候选方法封存清单.json'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
now=lambda:datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
assert record['status']=='completed_all_fixed_method_new_parameter_planned_attempts'
assert len(record['rows'])==record['planned_native_benchmark_attempts']==224
assert record['input_manifest_sha256']==sha(manifest_path)
assert manifest['method_manifest_sha256']==sha(method_path)
assert len(record['input_preflight'])==32 and all(json.loads(a['stdout'])['embedded_closed'] for a in record['input_preflight'])
def functions(path,names):
    """只加载无远程副作用的纯复算函数。"""
    module=ast.parse(path.read_text('utf8'));nodes=[n for n in module.body if isinstance(n,ast.FunctionDef) and n.name in names]
    scope={'np':np,'trimesh':trimesh,'pv':pv,'vtk':vtk}
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),scope);return scope
quality=functions(here/'04-原版生成阶段同输入基线.py',{'quality'})['quality']
utils=functions(here/'397-共面前清理十四输入全部质量几何速度复算.py',{'distances','timing'})
output=here/'451-固定原生方法十六新参数完整复算.json';assert not output.exists()
summary={'生成时间':now(),'修改时间及修改内容':'首次固定方法全部224新参数实际计划复算',
 '文档概述':'方法在新输入生成前固定；完整分母保留失败；有限表面距离不等于连续证书',
 '索引目录':['cases','all_repeat_quality','totals'],'status':'running','source_record_sha256':sha(record_path),
 'input_manifest_sha256':sha(manifest_path),'method_manifest_sha256':sha(method_path),
 'cases':[],'all_repeat_quality':[],'failed_attempts':[]}
def save():
    """逐输入保存已完成证据，未终态不能当完整统计。"""
    output.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n','utf8')
save()
for i,case in enumerate(manifest['cases']):
    row={'index':i,'case':case['id'],'kind':case['kind'],'input_parent_quality':quality(Path(case['parent'])),
      'parent_sha256':case['parent_sha256'],'tool_sha256':case['tool_sha256'],'methods':{}}
    first={}
    for method in ['baseline','candidate']:
        runs=[r for r in record['rows'] if r['case_index']==i and r['method']==method]
        assert len(runs)==7 and sorted(r['repeat'] for r in runs)==[-1,0,1,2,3,4,5]
        measured=[];first_quality=None
        for run in runs:
            if run['returncode']!=0:
                summary['failed_attempts'].append({'case_index':i,'method':method,'repeat':run['repeat'],
                 'returncode':run['returncode'],'subprocess_wall_ms':run['subprocess_wall_ms'],'log_sha256':run['log_sha256']})
                continue
            path=folder/f'{i:02d}'/Path(run['mesh_path']).name;assert sha(path)==run['mesh_sha256']
            q=quality(path);assert q['faces']==run['native_timing']['faces']
            summary['all_repeat_quality'].append({'case_index':i,'method':method,'repeat':run['repeat'],
              'mesh_sha256':sha(path),'quality':q})
            if run['repeat']>=0:measured.append(q)
            if run['repeat']==0:first[method]=path;first_quality=q
        measured_runs=[r for r in runs if r['repeat']>=0 and r['returncode']==0]
        value={'planned_calls':7,'returned_meshes':sum(r['returncode']==0 for r in runs),
          'failed_calls':sum(r['returncode']!=0 for r in runs),'quality':first_quality,
          'successful_measured_calls':len(measured_runs),'failed_measured_calls':6-len(measured_runs),
          'boolean_timing':utils['timing']([r['native_timing']['boolean_ms'] for r in measured_runs]) if measured_runs else None,
          'process_timing_all_measured':utils['timing']([r['subprocess_wall_ms'] for r in runs if r['repeat']>=0]),
          'repeat_quality_ranges':{key:{'min':min(q[key] for q in measured),'max':max(q[key] for q in measured)}
             for key in ['faces','below_10_faces','below_10_area_mm2','volume_mm3','nonpositive_or_nonfinite_faces']} if measured else None}
        if method in first:
            entry=next(a for a in record['native_audits'] if a['case_index']==i and a['method']==method)
            ap=folder/f'{i:02d}'/Path(entry['audit_path']).name;assert sha(ap)==entry['audit_sha256']
            assert sha(first[method])==entry['mesh_sha256']
            wrapped=json.loads(ap.read_text('utf8'));actual=json.loads(wrapped['stdout']) if wrapped['returncode']==0 else None
            value.update(first_output_audit=actual,first_output_embedded_closed=bool(actual and actual['embedded_closed']))
        row['methods'][method]=value
    if all(m in first for m in ['baseline','candidate']):
        b,c=[row['methods'][m]['quality'] for m in ['baseline','candidate']]
        row.update(bad_count_change=c['below_10_faces']-b['below_10_faces'],
                   bad_area_change_mm2=c['below_10_area_mm2']-b['below_10_area_mm2'])
        if b['faces']>0 and c['faces']>0:
            row['geometry']={'baseline_to_candidate':utils['distances'](first['baseline'],first['candidate'],2026100720+i),
              'candidate_to_baseline':utils['distances'](first['candidate'],first['baseline'],2026100750+i),
              'baseline_first_geometry_valid':row['methods']['baseline']['first_output_embedded_closed']}
    summary['cases'].append(row);save()
    print(i,case['id'],[(m,row['methods'][m]['returned_meshes'],row['methods'][m]['quality']['below_10_faces'] if row['methods'][m]['quality'] else None) for m in ['baseline','candidate']],flush=True)
assert len(summary['cases'])==16
assert len(summary['all_repeat_quality'])+len(summary['failed_attempts'])==224
summary.update(status='completed_all_224_planned_new_parameter_quality_geometry_timing_recomputations',
 finished_beijing=now(),totals={'planned_attempts':224,'returned_meshes':len(summary['all_repeat_quality']),
 'failed_attempts':len(summary['failed_attempts'])})
save();print(json.dumps(summary['totals'],ensure_ascii=False))
