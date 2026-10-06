"""独立观测薄壁第四刀正面积残余小面源的作者原三阶段，不修改原阶段二三拒绝。"""
from pathlib import Path
import json,hashlib,shutil,importlib.util,re
import trimesh
from run_constrained_batch import RemoteQuality
from run_geometry_study import execute,retrieve,save,now,PYTHON
from physical_source_before_encoding_audit import audit_physical_source
root=Path('D:/GraduationProject_切削排斥证据');project=Path.cwd()
load=lambda p:json.loads(p.read_text('utf8'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
rid='薄壁_00_长序列'
batch=root/'20261005_两处焊接修订薄壁完整32刀开发'/rid
row=load(batch/'01-统一配置完整父反馈记录.json')['rows'][3]
assert row['event']=='e3' and row['status']=='maintenance_input_rejected'
source=batch/(rid+'_e3_candidate_input')/'physical_source_2.obj'
assert sha(source)==row['physical_source_checks'][2]['saved_sha256'] and row['physical_source_checks'][2]['embedded_closed']
reference=root/'20261005_薄壁32刀相邻小面完整精确逐步参照生成'/rid/(rid+'_e3_reference')/'validated_reference.obj'
refrow=load(reference.parent.parent/'01-独立累计参照绑定.json')['rows'][3]
assert sha(reference)==refrow['reference_sha256']
previous=project/'初步实验/Geogram与PaMO切削排斥冻结_20261005_第三刀阶段二不默认焊接投影控制'
snapshot=project/'初步实验/Geogram与PaMO切削排斥冻结_20261005_薄壁第四刀正面积小面源原三阶段观测'
snapshot.mkdir(exist_ok=False)
for name in ['sdf_bias_remesh.py','normalized_sdf_chain.py','normalized_working_source_gate.py']:shutil.copyfile(previous/name,snapshot/name)
worker=(previous/'stage2_only_worker.py').read_text('utf8')
assert worker.count('use_stage1=False, use_stage3=True')==1
worker=worker.replace('use_stage1=False, use_stage3=True','use_stage1=True, use_stage3=True')
worker=worker.replace("'use_stage1': False","'use_stage1': True").replace("'stage1': 0, 'stage2': 1, 'stage3': 1","'stage1': 1, 'stage2': 1, 'stage3': 1")
worker=worker.replace("'actual_sdf_resolution': None","'actual_sdf_resolution': int(model.R)")
worker=worker.replace("'resolution': 768","'resolution': cfg['minimum_sdf_resolution']")
worker=worker.replace('01-第三刀修复源阶段二三GPU终态.json','01-薄壁第四刀原三阶段GPU诊断终态.json')
worker=worker.replace('原简化及安全投影，同一失败第三刀源；原始拒绝输出仅作观察，不是发布','作者原三阶段正面积源诊断；阶段二三原拒绝保留，输出门槛不放宽，不是发布')
spec=importlib.util.spec_from_file_location('budget',project/'初步实验/Geogram与PaMO切削排斥冻结_20261005_严格焊接与原拓扑完整反馈依赖修订/simplification_budget_ratio.py')
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
target,ratio=mod.target_budget(len(trimesh.load(source,process=False).faces),len(trimesh.load(reference,process=False).faces))
pattern=r'ratio=1\.151643690349947, min_verts=0'
assert len(re.findall(pattern,worker))==1
worker=re.sub(pattern,'ratio='+repr(ratio)+', min_verts=0',worker)
compile(worker,str(snapshot/'full_stage_worker.py'),'exec');(snapshot/'full_stage_worker.py').write_text(worker,'utf8')
shutil.copyfile(Path(__file__),snapshot/Path(__file__).name)
manifest=[{'file':p.name,'sha256':sha(p)} for p in sorted(snapshot.glob('*.py'))]
save(snapshot/'01-执行源码冻结清单.json',manifest)
output=root/'20261005_薄壁第四刀残余正面积小面源原三阶段GPU诊断';output.mkdir(exist_ok=False)
inputs=load(root/'20261005_新实例薄壁第三刀同源关闭阶段一GPU控制_v2/inputs.json')
inputs.update(source_override={'file':'source.obj','sha256':sha(source)},origin_override_mm=row['encoded_fragment_preparation']['fixed_operation_origin_mm'],minimum_sdf_resolution=640)
save(output/'inputs.json',inputs)
record={'生成时间':now(),'修改时间及修改内容':'首次生成，正面积小面源原三阶段诊断','文档概述':'不同于冻结阶段二三候选：正面积FP64物理及三份实际编码完整门控后才作原三阶段观察；不降低输出面积、排斥或拓扑门槛，不发布','索引目录':['bindings','execution'],'status':'running','target_faces':target,'input_small_faces':4,'original_stage23_rejection_preserved':True,'new_publications':0,'bindings':{str(p):sha(p) for p in [source,reference,batch/'01-统一配置完整父反馈记录.json',snapshot/'01-执行源码冻结清单.json']}}
report=output/'01-薄壁第四刀原三阶段执行登记.json';save(report,record)
e=RemoteQuality(output,14137)
try:
 assert execute(e.client,['mkdir',e.remote])['returncode']==0
 valid,metrics=audit_physical_source(e,output,trimesh.load(source,process=False),record)
 assert valid;record['input_positive_physical_audit']=metrics;save(report,record)
 for path in [snapshot/r['file'] for r in manifest]+[output/'inputs.json',source]:
  remote=e.remote+'/'+('source.obj' if path==source else path.name);e.sftp.put(str(path),remote);assert execute(e.client,['sha256sum',remote])['stdout'].split()[0]==sha(path)
 run=execute(e.client,['env','LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libstdc++.so.6',PYTHON,e.remote+'/full_stage_worker.py'],e.remote+'/stdout.log',timeout=900)
 retrieve(e.client,e.sftp,e.remote+'/stdout.log',output/'stdout.log')
 record.update(status='completed_with_recorded_outcomes',finished_beijing=now(),execution=run);save(report,record)
 for name in ['01-薄壁第四刀原三阶段GPU诊断终态.json','raw_full_candidate.obj']:
  try:retrieve(e.client,e.sftp,e.remote+'/result/'+name,output/name)
  except FileNotFoundError:pass
 for name in ['04-完整求解前实际工作源门控.json','01-CUDA初始编码源.obj','02-CUDA再中心化碰撞源.obj','03-整理后归一化SDF源.obj']:
  try:retrieve(e.client,e.sftp,e.remote+'/result/working_sources/'+name,output/name)
  except FileNotFoundError:pass
 print({'execution_returncode':run['returncode'],'output_present':(output/'raw_full_candidate.obj').exists()},flush=True)
finally:e.close()
