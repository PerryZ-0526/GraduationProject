"""复算20次同输入调用，输出几何与质量核查不替代完整速度分布。"""
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
z=zipfile.ZipFile(here/'631-免重复判定四类实际比较完整归档.zip')
assert z.testzip() is None
raw=z.read('01-免重复判定四类实际比较记录.json');record=json.loads(raw)
assert record['status']=='completed_all_twenty_diagnostic_calls' and len(record['rows'])==20
original_trimesh=trimesh
class ZipMesh:
    """原字节读取本次ZIP的保存网格，不重复解压。"""
    def load(self,path,**kwargs):
        return original_trimesh.load(io.BytesIO(z.read(Path(path).name)),file_type='obj',**kwargs)
trimesh=ZipMesh()
def functions(path,names):
    """只取既有无远程副作用的纯复算函数。"""
    tree=ast.parse(path.read_text('utf8'));nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
    scope={'np':np,'trimesh':trimesh,'pv':pv,'vtk':vtk}
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),scope);return scope
quality=functions(here/'04-原版生成阶段同输入基线.py',{'quality'})['quality']
utils=functions(here/'397-共面前清理十四输入全部质量几何速度复算.py',{'distances','timing'})
def tag(row):
    """文件名来自明确的工作器命名规则，摘要随后逐份核对。"""
    return f"{row['input_index']:02d}_"+('reference' if not row['profile'] else ('profile_warmup' if row['repeat']<0 else f"profile_r{row['repeat']:02d}"))
all_rows=[]
for r in record['rows']:
    assert r['returncode']==0 and r['embedded_closed']
    label=tag(r);mesh=z.read(label+'.obj');audit=z.read(label+'_audit.json')
    assert hashlib.sha256(mesh).hexdigest()==r['mesh_sha256']
    assert hashlib.sha256(audit).hexdigest()==r['audit_sha256']
    a=json.loads(audit);assert a['returncode']==0 and json.loads(a['stdout'])['embedded_closed']
    all_rows.append(dict(r,quality=quality(Path(label+'.obj'))))
cases=[]
for i in [13,10,4,7]:
    selected=[r for r in all_rows if r['input_index']==i];ref=next(r for r in selected if not r['profile'])
    measured=[r for r in selected if r['repeat']>=0];assert len(measured)==3
    first=measured[0]
    geometry={}
    for name,a,b in [('reference_to_candidate',ref,first),('candidate_to_reference',first,ref)]:
        # 固定种子只保证抽样可复算，不改变任一保存网格。
        geometry[name]=utils['distances'](Path(tag(a)+'.obj'),Path(tag(b)+'.obj'),2026100700+i)
    cases.append({'input_index':i,'case':ref['case'],'same_frozen_method_reference_timing':ref['native_timing'],
        'candidate_three_repeats_timing':utils['timing']([r['native_timing']['boolean_ms'] for r in measured]),
        'reference_quality':ref['quality'],'candidate_first_quality':first['quality'],
        'all_candidate_quality_ranges':{k:{'min':min(r['quality'][k] for r in measured),'max':max(r['quality'][k] for r in measured)} for k in ['faces','below_10_faces','below_10_area_mm2']},'geometry':geometry})
now=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
summary={'生成时间':now,'修改时间及修改内容':'首次免重复判定同输入20次保存输出复算','文档概述':'当前20保存对象均静态精确有效；旧副本单次参照、开发副本三次测量，不是完整或独立速度评价',
    '索引目录':['cases','rows'],'status':'completed_twenty_saved_native_calls_quality_geometry_recomputed',
    'archive_sha256':hashlib.sha256((here/'631-免重复判定四类实际比较完整归档.zip').read_bytes()).hexdigest(),
    'source_record_sha256':hashlib.sha256(raw).hexdigest(),'actual_calls':20,'exact_valid':20,'cases':cases,'rows':all_rows}
(here/'639-免重复判定四类保存质量速度完整统计.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n','utf8')
for c in cases:print(c['input_index'],c['same_frozen_method_reference_timing']['boolean_ms'],c['candidate_three_repeats_timing'],c['reference_quality']['below_10_faces'],c['candidate_first_quality']['below_10_faces'])
