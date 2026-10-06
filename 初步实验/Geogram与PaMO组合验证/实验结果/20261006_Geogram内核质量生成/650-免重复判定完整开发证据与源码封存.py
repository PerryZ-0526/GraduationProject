"""封存本次实际副本及完整证据，不覆盖旧方法或改写独立评价身份。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json
import shutil
import difflib

here=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
stats=json.loads((here/'649-免重复判定十六已见三方法完整统计.json').read_text('utf8'))
ct=json.loads((here/'641-免重复判定原生CT十六刀保存联合复算.json').read_text('utf8'))
assert stats['status']=='completed_all_336_saved_native_calls_quality_geometry_timing_recomputed'
assert all(stats['totals'][m]['exact_valid']==112 for m in ['baseline','previous','candidate'])
assert ct['totals']['accepted']==16 and ct['totals']['rejected']==ct['totals']['blocked']==0
build_path=here/'625-已保留接缝顶点免重复判定原生构建记录.json'
build=json.loads(build_path.read_text('utf8'))
source_manifest=json.loads((here/'620-已保留接缝顶点免重复判定源码清单.json').read_text('utf8'))
folder=here/'免重复判定当前原生候选封存';folder.mkdir()
for name,digest in source_manifest['files'].items():
    source=here/'第二十四轮已保留接缝顶点免重复判定'/name;assert sha(source)==digest
    assert build['candidate_source_hashes']['src/lib/geogram/mesh/'+name]==digest
    shutil.copy2(source,folder/name)
for name in ['03-原生布尔质量与阶段计时.cpp','621-已保留接缝顶点免重复判定独立编译.py']:
    shutil.copy2(here/name,folder/name)
before=(here/'新边拒绝固定原生候选封存/mesh_surface_intersection_internal.cpp').read_text('utf8')
after=(folder/'mesh_surface_intersection_internal.cpp').read_text('utf8')
diff=''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='569封存原内核',tofile='免重复判定内核'))
assert 'if(keep_vertex_[v2])' in diff and 'v1 = v2;' in diff
now=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
evidence=['649-免重复判定十六已见三方法完整统计.json','641-免重复判定原生CT十六刀保存联合复算.json',
    '639-免重复判定四类保存质量速度完整统计.json','625-已保留接缝顶点免重复判定原生构建记录.json',
    '620-已保留接缝顶点免重复判定源码清单.json','569-新边拒绝原生主候选完整开发终态封存清单.json',
    '582-新边拒绝固定方法第二批十六新参数完整复算.json','618-稳定原生四类阶段诊断完整统计.json']
record={'生成时间':now,'修改时间及修改内容':'首次免重复判定实际副本完整开发后封存',
    '文档概述':'实际原生布尔质量生成；16已见输入336三方法全部精确通过、当前反馈16/16；不是任意输入或新方法未见评价保证',
    '索引目录':['files','evidence','semantic_change','reproduction_limits'],'status':'frozen_current_native_optimization_after_complete_seen16_and_ct16',
    'remote_native_root':'/tmp/geogram_native_quality_20261007_32','build_sha256':sha(build_path),
    'candidate_binary_sha256':build['candidate_binary_sha256'],'candidate_library_sha256':build['candidate_library_sha256'],
    'files':{p.name:sha(p) for p in folder.iterdir()},'evidence':{name:sha(here/name) for name in evidence},
    'semantic_change':diff,'reproduction_limits':'五份源码冻结不是独立跨环境安装包；实际构建脚本仍读取远端02号2300文件源码与已编译原版，复现需同一冻结依赖或另行完整源码打包。',
    'goal_status':'整体大幅质量改善与可接受速度尚未全部成立；先列完整统计，由用户之后确定速度标准'}
(here/'651-免重复判定当前原生候选完整证据封存.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n','utf8')
print('frozen_actual_native_candidate_with_complete_evidence')
