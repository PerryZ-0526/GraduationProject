"""冻结第三刀严格焊接修复源的阶段二三GPU控制，不计连续发布。"""
from pathlib import Path
import json,hashlib,shutil,importlib.util
import trimesh,numpy as np
from run_constrained_batch import RemoteQuality
from run_geometry_study import execute,retrieve,save,now,PYTHON
root=Path('D:/GraduationProject_切削排斥证据'); project=Path.cwd()
load=lambda p:json.loads(p.read_text('utf8'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
repair=root/'20261005_第三刀严格同坐标源原预算邻面修复开发'
repair_record=load(repair/'01-第三刀严格焊接同源修复控制.json')
assert repair_record['accepted_for_new_GPU_control'] and repair_record['final_source_guard_passed']
source=repair/'prepared_source.obj'
assert sha(source)==repair_record['candidate_sha256']
reference=root/'20261005_薄壁32刀相邻小面完整精确逐步参照生成/薄壁_00_长序列/薄壁_00_长序列_e2_reference/validated_reference.obj'
reference_row=load(reference.parent.parent/'01-独立累计参照绑定.json')['rows'][2]
assert reference_row['event']=='e2' and sha(reference)==reference_row['reference_sha256']
previous=project/'初步实验/Geogram与PaMO切削排斥冻结_20261005_五小面邻面修复源阶段二三观测'
snapshot=project/'初步实验/Geogram与PaMO切削排斥冻结_20261005_第三刀严格焊接修复源阶段二三观测'
snapshot.mkdir(exist_ok=False)
for name in ['sdf_bias_remesh.py','normalized_sdf_chain.py','normalized_working_source_gate.py']:
    shutil.copyfile(previous/name,snapshot/name)
# 仅按同一独立参照重算面预算，并将新增控制的说明改为第三刀。
spec=importlib.util.spec_from_file_location('budget',project/'初步实验/Geogram与PaMO切削排斥冻结_20261005_邻面约束小面修复完整反馈/simplification_budget_ratio.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
target,ratio=module.target_budget(len(trimesh.load(source,process=False).faces),len(trimesh.load(reference,process=False).faces))
worker=(previous/'stage2_only_worker.py').read_text('utf8')
assert worker.count('ratio=0.7768595041322314, min_verts=0')==1
worker=worker.replace('ratio=0.7768595041322314, min_verts=0','ratio='+repr(ratio)+', min_verts=0')
worker=worker.replace('第二刀','第三刀').replace('01-修复源阶段二三GPU终态.json','01-第三刀修复源阶段二三GPU终态.json')
compile(worker,str(snapshot/'stage2_only_worker.py'),'exec')
(snapshot/'stage2_only_worker.py').write_text(worker,'utf8')
shutil.copyfile(Path(__file__),snapshot/Path(__file__).name)
manifest=[{'file':p.name,'sha256':sha(p)} for p in sorted(snapshot.glob('*.py'))]
save(snapshot/'01-执行源码冻结清单.json',manifest)
output=root/'20261005_第三刀严格焊接修复源阶段二三GPU对照';output.mkdir(exist_ok=False)
inputs=load(root/'20261005_新实例薄壁第三刀同源关闭阶段一GPU控制_v2/inputs.json')
# 此事件旧流程在清理处终止；原点取本事件严格焊接源三角均值，并显式绑定。
original=trimesh.load(root/'20261005_第三刀八位重复面与严格同坐标焊接诊断/exact_weld_source.obj',process=False)
origin=np.asarray(original.triangles_center).mean(axis=0)
inputs.update(source_override={'file':'source.obj','sha256':sha(source)},origin_override_mm=origin.tolist(),minimum_sdf_resolution=640)
save(output/'inputs.json',inputs)
report=output/'01-第三刀GPU控制执行登记.json'
record={'生成时间':now(),'修改时间及修改内容':'首次生成，严格焊接修复源GPU控制','文档概述':'冻结作者阶段二三及同参照面预算；不是新连续发布','索引目录':['bindings','execution'],'status':'running','target_faces':target,'origin_rule':'third_event_exact_weld_source_triangle_mean','new_publications':0,'bindings':{'source_sha256':sha(source),'reference_sha256':sha(reference),'repair_record_sha256':sha(repair/'01-第三刀严格焊接同源修复控制.json'),'manifest_sha256':sha(snapshot/'01-执行源码冻结清单.json')}}
save(report,record)
engine=RemoteQuality(output,14137)
try:
    assert execute(engine.client,['mkdir',engine.remote])['returncode']==0
    for path in [snapshot/r['file'] for r in manifest]+[output/'inputs.json',source]:
        remote=engine.remote+'/'+('source.obj' if path==source else path.name)
        engine.sftp.put(str(path),remote)
        assert execute(engine.client,['sha256sum',remote])['stdout'].split()[0]==sha(path)
    log=engine.remote+'/stdout.log'
    run=execute(engine.client,['env','LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libstdc++.so.6',PYTHON,engine.remote+'/stage2_only_worker.py'],log,timeout=900)
    retrieve(engine.client,engine.sftp,log,output/'stdout.log')
    record.update(status='completed_with_recorded_outcomes',execution=run,finished_beijing=now())
    save(report,record)
    if run['returncode']==0:
        for name in ['01-第三刀修复源阶段二三GPU终态.json','raw_full_candidate.obj']:
            retrieve(engine.client,engine.sftp,engine.remote+'/result/'+name,output/name)
        terminal=load(output/'01-第三刀修复源阶段二三GPU终态.json')
        assert terminal['output_sha256']==sha(output/'raw_full_candidate.obj')
        print({k:terminal[k] for k in ['stage_calls','finite','zero_or_small_faces','euler','components','embedding']},flush=True)
    else:
        print({'execution_returncode':run['returncode']},flush=True)
finally:
    engine.close()
