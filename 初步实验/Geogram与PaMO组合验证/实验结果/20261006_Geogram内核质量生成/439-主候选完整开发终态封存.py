"""在完整十四开发例与十六刀保存复审终态后冻结主候选，保留失败优化。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json
import shutil

here=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
source_manifest=here/'370-共面重建前合法新边清理源码清单.json'
build_path=here/'375-共面重建前清理实际原生编译记录.json'
summary_path=here/'398-共面前清理原生十四同输入完整复算.json'
audit_path=here/'十四输入全部196保存重复准确复审/01-全部196保存对象准确复审记录.json'
feedback_path=here/'384-共面前清理原生CT十六刀保存联合复算.json'
source=json.loads(source_manifest.read_text('utf8'));build=json.loads(build_path.read_text('utf8'))
summary=json.loads(summary_path.read_text('utf8'));audit=json.loads(audit_path.read_text('utf8'))
feedback=json.loads(feedback_path.read_text('utf8'))
assert build['status']=='completed_candidate_build_with_verified_original_baseline_reuse'
assert build['source_manifest_sha256']==sha(source_manifest)
assert summary['status']=='completed_all_196_saved_quality_recomputations_and_fourteen_geometry_timing_pairs'
assert audit['status']=='completed_all_196_saved_object_exact_audits'
assert audit['totals']['candidate']=={'total':98,'embedded_closed':98}
assert feedback['totals']['accepted']==16 and feedback['totals']['rejected']==0 and feedback['totals']['blocked']==0
rejected=json.loads((here/'419-好面免重建原生CT十六刀保存联合复算.json').read_text('utf8'))
assert rejected['totals']['accepted']==0 and rejected['totals']['rejected']==1
folder=here/'共面前清理固定原生候选封存';folder.mkdir()
for name,digest in source['files'].items():
    original=here/'第二十轮共面重建前合法新边清理'/name;assert sha(original)==digest
    shutil.copy2(original,folder/name)
    assert build['candidate_source_hashes']['src/lib/geogram/mesh/'+name]==digest
for name in ['03-原生布尔质量与阶段计时.cpp','371-共面重建前清理原生独立编译.py']:
    shutil.copy2(here/name,folder/name)
now=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
record={'生成时间':now,'修改时间及修改内容':now+'，完整开发终态后第一次方法封存',
 '文档概述':'二十轮为主候选；二十一轮首刀开放和自交负例不交付；新参数评价前冻结',
 '索引目录':['method','files','evidence'],'status':'frozen_native_method_before_new_parameter_evaluation',
 'method':{'remote_root':'/tmp/geogram_native_quality_20261006_21',
 'source_manifest_sha256':sha(source_manifest),'build_sha256':sha(build_path),
 'candidate_binary_sha256':build['candidate_binary_sha256'],'candidate_library_sha256':build['candidate_library_sha256'],
 'baseline_binary_sha256':build['baseline_binary_sha256'],'baseline_library_sha256':build['baseline_library_sha256'],
 'parameters':{'diagnostic_small_angle_deg':10,'triangle_target_deg':20,'interior_added_point_budget':64,
 'conditional_boundary_point_budget':128,'strip_design_deg':15,'max_strip_slices':64,
 'max_strip_boundary_points':126,'machine_length_epsilon_multiplier':128,
 'machine_planar_normal_angle_deg':1e-5,'original_distinct_coordinate_merge_forbidden':True,
 'retained_face_orientation_must_be_positive':True,'disjoint_one_ring_each_pass':True,
 'pre_and_post_coplanar_cleanup':True,'quality_gate_bad_count_and_absolute_area':True}},
 'files':{p.name:sha(p) for p in folder.iterdir() if p.is_file()},
 'evidence':{'complete_development_summary_sha256':sha(summary_path),'all_development_audit_sha256':sha(audit_path),
 'complete_feedback_summary_sha256':sha(feedback_path),'rejected_skip_group_summary_sha256':sha(here/'419-好面免重建原生CT十六刀保存联合复算.json')},
 'new_evaluation_policy':'方法和全部参数固定；新案例提前一次生成与冻结，评价后不能据其修改此方法或移除失败',
 'speed_policy':'先报告完整中位、P95、最大和网格规模，用户确定速度标准；研究30秒防失控上限不作为速度合格值'}
(here/'440-固定原生主候选方法封存清单.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n','utf8')
print('frozen_native_method_after_complete_development',len(record['files']))
