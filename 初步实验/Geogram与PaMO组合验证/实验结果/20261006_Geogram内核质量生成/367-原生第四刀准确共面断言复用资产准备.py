"""冻结最新原生连续第四刀实际输入与失败日志，供后续同源复现。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json
import shutil

here=Path(__file__).resolve().parent
folder=here/'原生第四刀准确共面断言复用资产';folder.mkdir()
source=here/'逐轮新边修复原生CT十六刀全部实际输出'
record_path=source/'01-原生CT十六刀反馈实际记录.json'
record=json.loads(record_path.read_text('utf8'));event=record['events'][3]
assert event['status']=='rejected_native_output' and event['methods']['candidate']['returncode']==1
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
parent=source/Path(event['parent_path']).name;assert sha(parent)==event['parent_sha256']
tool=here/'原生CT十六刀开发冻结输入/03_tool.obj';assert sha(tool)==event['tool_sha256']
log=source/'e03_candidate.log';assert sha(log)==event['methods']['candidate']['log_sha256']
assert '!Q.empty()' in log.read_text('utf8') and 'CDT_2d.cpp' in log.read_text('utf8')
mapping={'00-真实第三刀有效父网格.obj':parent,'01-真实第四刀工具.obj':tool,
 '02-原生候选第四刀实际失败日志.txt':log,
 '03-原版同父第四刀输出.obj':source/'e03_baseline.obj',
 '04-原版同父第四刀精确审计.json':source/'e03_baseline_audit.json',
 '05-实际原生编译记录.json':here/'341-逐轮新边收缩实际原生编译记录.json',
 '06-实际源码清单.json':here/'336-互斥邻域逐轮新边收缩源码清单.json'}
for name,p in mapping.items():shutil.copy2(p,folder/name)
for name in ['mesh_surface_intersection.cpp','mesh_surface_intersection_internal.cpp','mesh_surface_intersection_internal.h']:
    shutil.copy2(here/'第十九轮新边收缩互斥邻域逐轮复查'/name,folder/name)
now=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
manifest={'生成时间':now,'修改时间及修改内容':now+'，首次绑定原生第四刀准确共面断言',
 '文档概述':'真实已见开发负例，前父有效；候选自然断言失败，原版返回但同保存对象不嵌入',
 '索引目录':['files','failure','symbol_location'],'status':'frozen_actual_native_fourth_event_assertion_scene',
 'source_record_sha256':sha(record_path),'parent_sha256':sha(parent),'tool_sha256':sha(tool),
 'failure':event['methods']['candidate'],
 'symbol_location':{'library_offset_0x26c03a':'GEO::CoplanarFacets::triangulate()',
  'library_offset_0x256824':'GEO::MeshSurfaceIntersection::simplify_coplanar_facets(double) parallel lambda',
  'resolution':'实际原运行库addr2line -f -C；Release没有源码行信息，断言本身报告CDT_2d.cpp:610'},
 'files':{p.name:sha(p) for p in folder.iterdir() if p.is_file()}}
(here/'368-原生第四刀准确共面断言复用资产清单.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n','utf8')
print('frozen_actual_fourth_event_scene',len(manifest['files']))
