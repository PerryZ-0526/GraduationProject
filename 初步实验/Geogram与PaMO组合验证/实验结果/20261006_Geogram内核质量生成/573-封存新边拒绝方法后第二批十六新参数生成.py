"""方法封存后一次生成十六新参数，含旋转与真实已见CT的新位置，尚不打开候选输出。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import ast
import hashlib
import json
import math
import numpy as np
import trimesh

here=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
method_path=here/'569-新边拒绝原生主候选完整开发终态封存清单.json'
method=json.loads(method_path.read_text('utf8'));assert method['status']=='frozen_native_method_after_complete_seen_development_before_future_new_evaluation'
for name,digest in method['files'].items():assert sha(here/'新边拒绝固定原生候选封存'/name)==digest
folder=here/'新边拒绝固定方法第二批新参数十六输入封存';folder.mkdir()
generator_path=here.parents[1]/'freeze_followup_inputs.py'
module=ast.parse(generator_path.read_text('utf8'))
function=next(n for n in module.body if isinstance(n,ast.FunctionDef) and n.name=='torus_mesh')
scope={'math':math,'trimesh':trimesh};exec(compile(ast.Module(body=[function],type_ignores=[]),str(generator_path),'exec'),scope)
torus=scope['torus_mesh']
seed=2026100704;rng=np.random.default_rng(seed);cases=[]
def write(mesh,path):
    """保存17位双精度输入，重载后逐位一致并核对基本拓扑，不预判候选结果。"""
    with path.open('x',encoding='utf8',newline='\n') as stream:
        for x,y,z in mesh.vertices:stream.write(f'v {x:.17g} {y:.17g} {z:.17g}\n')
        for a,b,c in mesh.faces:stream.write(f'f {a+1} {b+1} {c+1}\n')
    saved=trimesh.load(path,process=False,force='mesh')
    assert np.array_equal(saved.vertices,mesh.vertices) and np.array_equal(saved.faces,mesh.faces)
    assert saved.is_watertight and saved.is_winding_consistent and saved.volume>0
    assert np.isfinite(saved.vertices).all() and (saved.area_faces>0).all()
def add(name,kind,parent,tool,parameters,rotate=False):
    """新旋转和偏移同时施于父与工具，明确记录，不选择有利输出。"""
    if rotate:
        axis=rng.normal(size=3);axis/=np.linalg.norm(axis);angle=float(rng.uniform(.17,1.27))
        transform=trimesh.transformations.rotation_matrix(angle,axis)
        transform[:3,3]=rng.uniform(-.55,.55,3)
        parent.apply_transform(transform);tool.apply_transform(transform)
        parameters.update(shared_transform=transform.tolist(),rotation_angle_radians=angle)
    i=len(cases);pp=folder/f'{i:02d}_parent.obj';tp=folder/f'{i:02d}_tool.obj'
    write(parent,pp);write(tool,tp)
    cases.append({'id':name,'kind':kind,'role':'method_frozen_new_parameter_evaluation',
      'parent':str(pp),'tool':str(tp),'parent_sha256':sha(pp),'tool_sha256':sha(tp),'parameters':parameters})
for i,(face_id,radius,depth) in enumerate([(207,.219,.042),(631,.317,.062),(927,.407,.093),(1099,.491,.113)]):
    parent=trimesh.creation.icosphere(subdivisions=3,radius=float(rng.uniform(4.7,5.8)))
    scale=rng.uniform(.87,1.19,3);parent.vertices*=scale
    center=parent.triangles_center[face_id]+parent.face_normals[face_id]*depth+rng.uniform(-.00043,.00043,3)
    tool=trimesh.creation.icosphere(subdivisions=2,radius=radius);tool.vertices+=center
    add(f'独立新参数普通切口_{i:02d}','普通切口',parent,tool,{'face_id':face_id,'scale':scale.tolist(),'tool_center_mm':center.tolist(),'tool_radius_mm':radius,'depth_mm':depth})
for i,width in enumerate([.026,.051,.074]):
    parent=trimesh.creation.box(extents=(2.41,1.83,width));radius=.051+.0045*i
    center=np.array([.1531-.011*i,-.0973+.013*i,width/2+.029+.003*i])
    tool=trimesh.creation.icosphere(subdivisions=3,radius=radius);tool.vertices+=center
    add(f'独立旋转薄壁_{width:.3f}毫米','薄壁',parent,tool,{'width_mm':width,'extents_mm':[2.41,1.83,width],'tool_radius_mm':radius,'unrotated_tool_center_mm':center.tolist()},True)
for i,width in enumerate([.031,.057,.087]):
    left=trimesh.creation.box(extents=(1.23,2.17,1.07));right=left.copy()
    left.apply_translation([-(1.23+width)/2,0,0]);right.apply_translation([(1.23+width)/2,0,0])
    parent=trimesh.util.concatenate([left,right]);radius=.061+.0037*i
    center=np.array([-.411-.017*i,-.027+.014*i,1.07/2+.033+.0035*i])
    tool=trimesh.creation.icosphere(subdivisions=3,radius=radius);tool.vertices+=center
    add(f'独立旋转窄缝_{width:.3f}毫米','窄缝',parent,tool,{'width_mm':width,'tool_radius_mm':radius,'unrotated_tool_center_mm':center.tolist()},True)
for i,(width,minor) in enumerate([(.031,.435),(.061,.495),(.097,.575)]):
    major=minor+width/2;parent=torus(major,minor);radius=.053+.0065*i
    center=np.array([major+.0031+.0003*i,-.0041+.0004*i,minor+.035+.0045*i])
    tool=trimesh.creation.icosphere(subdivisions=3,radius=radius);tool.vertices+=center
    add(f'独立旋转贯通孔_{width:.3f}毫米','贯通孔',parent,tool,{'width_mm':width,'major_radius_mm':major,'minor_radius_mm':minor,'tool_radius_mm':radius,'unrotated_tool_center_mm':center.tolist()},True)
initial=here/'原生CT十六刀开发冻结输入/00_initial.obj'
for i,(face_id,radius,depth) in enumerate([(17031,.309,.052),(29407,.507,.095),(38763,.733,.119)]):
    parent=trimesh.load(initial,process=False,force='mesh')
    center=parent.triangles_center[face_id]+parent.face_normals[face_id]*depth+rng.uniform(-.00031,.00031,3)
    tool=trimesh.creation.icosphere(subdivisions=3,radius=radius);tool.vertices+=center
    add(f'已见CT新位置与工具_{i:02d}','CT已见患者新参数',parent,tool,{'initial_source_sha256':sha(initial),'face_id':face_id,'tool_radius_mm':radius,'tool_center_mm':center.tolist(),'depth_mm':depth})
assert len(cases)==16
development=json.loads((here/'526-新边拒绝三十已见输入回归冻结清单.json').read_text('utf8'))
old_pairs={(c['parent_sha256'],c['tool_sha256']) for c in development['cases']}
assert all((c['parent_sha256'],c['tool_sha256']) not in old_pairs for c in cases)
assert len({(c['parent_sha256'],c['tool_sha256']) for c in cases})==16
now=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
record={'生成时间':now,'修改时间及修改内容':now+'，封存方法之后首次生成并固定全部新参数',
 '文档概述':'16参数首次候选评价，形状家族已见；3CT为已见患者的新工具与位置，不称新患者',
 '索引目录':['cases','benchmark'],'status':'frozen_new_parameter_inputs_before_native_outputs',
 'seed':seed,'method_manifest_sha256':sha(method_path),'generator_sha256':sha(Path(__file__)),
 'torus_generator_sha256':sha(generator_path),'candidate_source_manifest_sha256':method['method']['source_manifest_sha256'],
 'benchmark':{'random_seed':2026100705,'repeats_per_method_per_case':6,'cpu_affinity_logical_processors':4},
 'cases':cases,'planned_native_benchmark_attempts':224,'tuning_after_evaluation_started':False,
 'input_check_scope':'全输入重载逐位一致、有限、正面积、闭合绕序；全量准确检查需远端预审；尚无原版或候选生成结果',
 'family_scope':'普通椭球、旋转薄壁/窄缝/环面及已见CT新切口；不称任意输入保证'}
(here/'574-新边拒绝固定方法第二批十六新参数运行前冻结清单.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n','utf8')
print('frozen_sixteen_new_parameter_cases_before_any_native_output')
