"""合并原十四开发例与已打开十六评价例，新版本只作已见回归。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json

here=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
cases=[]
for name in ['391-原生十四同输入含第四刀断言负例冻结清单.json','442-固定方法新参数十六输入运行前冻结清单.json']:
    prior=json.loads((here/name).read_text('utf8'))
    for old in prior['cases']:
        case=dict(old);case['role']='evaluation_opened_seen_development_regression';case['prior_manifest']=name
        for role in ['parent','tool']:assert sha(Path(case[role]))==case[role+'_sha256']
        cases.append(case)
assert len(cases)==30
manifest={'生成时间':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),
 '修改时间及修改内容':'首次新边拒绝版30个已见输入完整回归冻结',
 '文档概述':'不声称独立评价；保存全部失败、成功与原版比较',
 '索引目录':['cases','benchmark'],'status':'frozen_seen_development_regression_inputs',
 'method_manifest_sha256':sha(here/'508-递归前机器新边拒绝版本源码清单.json'),
 'cases':cases,'benchmark':{'random_seed':2026100703,'repeats_per_method_per_case':6,'cpu_affinity_logical_processors':4}}
(here/'526-新边拒绝三十已见输入回归冻结清单.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n','utf8')
worker=(here/'444-固定原生方法十六新参数完整交错评价.py').read_text('utf8')
start=worker.index("fixed=json.loads(");end=worker.index('diagnosis=Path(',start)
binding='''# 新开发方法源码、库和二进制在首次生成前逐项核查，不复用旧方法身份。
native_root=Path('/tmp/geogram_native_quality_20261007_27')
expected=json.loads((root/'source_manifest.json').read_text('utf8'))
assert sha(root/'source_manifest.json')==manifest['method_manifest_sha256']
assert sha(native_root/'build_record.json')==sha(build_path)
for name,digest in expected['files'].items():
    assert sha(native_root/'candidate_source/src/lib/geogram/mesh'/name)==digest
assert sha(native_root/'candidate_build/lib/libgeogram.so')==build['candidate_library_sha256']
assert sha(Path('/tmp/geogram_native_quality_20261006_02/baseline_build/lib/libgeogram.so'))==build['baseline_library_sha256']

'''
worker=worker[:start]+binding+worker[end:]
worker=worker.replace('第二十轮实际构建绑定候选修订','第二十二轮实际构建绑定候选修订')
worker=worker.replace('01-固定方法十六新参数交错质量速度记录','01-新边拒绝三十已见输入交错质量速度记录')
worker=worker.replace('224','420').replace('completed_all_fixed_method_new_parameter_planned_attempts','completed_all_thirty_seen_development_planned_attempts')
(here/'527-新边拒绝三十已见输入完整交错回归.py').write_text(worker,'utf8')
controller=(here/'445-固定方法十六新参数评价上传取回.py').read_text('utf8')
start=controller.index('fixed_path=');end=controller.index("receipt=",start)
controller=controller[:start]+'''native='/tmp/geogram_native_quality_20261007_27'
manifest_path=here/'526-新边拒绝三十已见输入回归冻结清单.json'
manifest=json.loads(manifest_path.read_text('utf8'))
source_path=here/'508-递归前机器新边拒绝版本源码清单.json'
assert manifest['method_manifest_sha256']==sha(source_path)
'''+controller[end:]
controller=controller.replace('sha(fixed_path)','sha(source_path)').replace("sftp.put(str(fixed_path),root+'/fixed_method.json')","sftp.put(str(source_path),root+'/source_manifest.json')")
for old,new in [('20261007_23','20261007_28'),('446-固定方法十六新参数评价实际取回记录','529-新边拒绝三十已见回归实际取回记录'),('444-固定原生方法十六新参数完整交错评价','527-新边拒绝三十已见输入完整交错回归'),('449-固定方法新参数实际运行构建记录','532-新边拒绝三十已见回归实际构建记录'),('447-固定方法十六新参数完整评价控制台日志','530-新边拒绝三十已见回归控制台日志'),('448-固定方法十六新参数全部实际输出','531-新边拒绝三十已见回归全部实际输出'),('固定方法十六新参数全部实际输出','新边拒绝三十已见回归全部实际输出'),('01-固定方法十六新参数交错质量速度记录','01-新边拒绝三十已见输入交错质量速度记录')]:controller=controller.replace(old,new)
controller=controller.replace('只读复用已验证的方法和原版','只读复用新开发方法和原版').replace('输出第一次打开后不调参','全部输入已打开，只作开发回归').replace('首次固定方法新参数全部计划评价','首次新开发方法三十已见输入全部计划回归')
(here/'528-新边拒绝三十已见回归上传执行取回.py').write_text(controller,'utf8')
recompute=(here/'450-固定方法十六新参数全部质量几何速度复算.py').read_text('utf8')
for old,new in [('固定方法十六新参数全部实际输出','新边拒绝三十已见回归全部实际输出'),('01-固定方法十六新参数交错质量速度记录','01-新边拒绝三十已见输入交错质量速度记录'),('442-固定方法新参数十六输入运行前冻结清单','526-新边拒绝三十已见输入回归冻结清单'),('440-固定原生主候选方法封存清单','508-递归前机器新边拒绝版本源码清单'),('451-固定原生方法十六新参数完整复算','534-新边拒绝三十已见输入完整复算'),('completed_all_fixed_method_new_parameter_planned_attempts','completed_all_thirty_seen_development_planned_attempts'),('224','420'),('==32','==60'),('==16','==30'),('方法在新输入生成前固定','新方法运行前固定，全部输入已见，不声称独立评价'),('首次固定方法全部','首次新开发版全部')]:recompute=recompute.replace(old,new)
(here/'533-新边拒绝三十已见全部质量几何速度复算.py').write_text(recompute,'utf8')
print('prepared',len(cases),'cases',420,'attempts')
