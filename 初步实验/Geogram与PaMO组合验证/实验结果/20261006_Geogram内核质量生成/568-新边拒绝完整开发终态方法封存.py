"""完整开发终态后封存本版，后续独立评价不得反向修改本版。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json
import hashlib
import shutil

here=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
development=here/'565-新边拒绝三十已见原归档完整复算.json'
audits=here/'新边拒绝三十已见全部保存准确复审/01-420计划实际保存对象准确复审记录.json'
feedback=here/'567-新边拒绝CT确定后缀完整保存联合复算.json'
d=json.loads(development.read_text('utf8'));a=json.loads(audits.read_text('utf8'));f=json.loads(feedback.read_text('utf8'))
assert d['totals']=={'planned_attempts':420,'returned_meshes':420,'failed_attempts':0}
assert a['totals']['candidate']=={'planned_attempts':210,'total':210,'embedded_closed':210}
assert f['totals']['accepted']==16 and f['totals']['rejected']==f['totals']['blocked']==0
assert f['verified_copied_prefix_events']==15 and f['actual_recovery_events']==1
build=json.loads((here/'513-递归前机器新边拒绝实际原生编译记录.json').read_text('utf8'))
manifest=json.loads((here/'508-递归前机器新边拒绝版本源码清单.json').read_text('utf8'))
assert build['source_manifest_sha256']==sha(here/'508-递归前机器新边拒绝版本源码清单.json')
folder=here/'新边拒绝固定原生候选封存';folder.mkdir()
for name,digest in manifest['files'].items():
    source=here/'第二十二轮递归前机器新边拒绝'/name
    assert sha(source)==digest==build['candidate_source_hashes']['src/lib/geogram/mesh/'+name]
    shutil.copy2(source,folder/name)
for name in ['03-原生布尔质量与阶段计时.cpp','509-递归前机器新边拒绝原生独立编译.py']:
    shutil.copy2(here/name,folder/name)
prior=json.loads((here/'440-固定原生主候选方法封存清单.json').read_text('utf8'))
parameters=dict(prior['method']['parameters'])
parameters['reject_unqualified_boundary_proposal_with_machine_new_edge_before_recursive_cdt']=True
record={'生成时间':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),
 '修改时间及修改内容':'首次新边拒绝原生方法在完整三十开发及十六反馈终态后封存',
 '文档概述':'当前可复现候选，全部开发输入已见；原独立评价十五成功一失败保持；新方法独立评价仍待完成',
 '索引目录':['method','files','evidence'],'status':'frozen_native_method_after_complete_seen_development_before_future_new_evaluation',
 'method':{'remote_root':'/tmp/geogram_native_quality_20261007_27',
    'build_sha256':sha(here/'513-递归前机器新边拒绝实际原生编译记录.json'),
    'source_manifest_sha256':sha(here/'508-递归前机器新边拒绝版本源码清单.json'),
    'candidate_binary_sha256':build['candidate_binary_sha256'],'candidate_library_sha256':build['candidate_library_sha256'],
    'baseline_binary_sha256':build['baseline_binary_sha256'],'baseline_library_sha256':build['baseline_library_sha256'],
    'parameters':parameters},
 'files':{p.name:sha(p) for p in folder.iterdir() if p.is_file()},
 'evidence':{p.name:sha(p) for p in [development,audits,feedback,here/'553-新边拒绝CT磁盘中断时远端原始记录.json',here/'551-实际插点近点与缓存有理数复审记录.json']},
 'speed_policy':'先报告完整最小、中位、P95、最大和输出规模，用户确定速度标准；不新增硬验收值',
 'new_evaluation_policy':'全部三十输入已见；新独立参数须在本封存后生成与冻结；不据未来评价修改本版',
 'environment_recovery_policy':'原十五刀进程因本机磁盘写满后断连失败；只恢复确证未执行末刀；旧进程状态和原字节保留，不把旧失败改成完成'}
output=here/'569-新边拒绝原生主候选完整开发终态封存清单.json';assert not output.exists()
output.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n','utf8')
print('frozen',len(record['files']),'files')
