"""分离近共面质量触发改动，只在已见旧第二刀来源版本上接入新边修复。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json

here=Path(__file__).resolve().parent
source=here/'第十五轮共边受影响区域限定再生成'
current=here/'第十七轮机器尺度新边受约束收缩'
output=here/'第十八轮原共面分组单独绑定新边收缩';output.mkdir()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
prior_path=here/'241-共边受影响区域限定再生成源码清单.json'
prior=json.loads(prior_path.read_text('utf8'))
for name,digest in prior['files'].items():
    assert sha(source/name)==digest
    # 新边修复只在主文件，另外两份恢复原有分组，不能将两项变化混为单项归因。
    origin=current/name if name=='mesh_surface_intersection.cpp' else source/name
    (output/name).write_bytes(origin.read_bytes())
now=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
manifest=here/'313-原共面分组单独新边收缩源码清单.json'
manifest.write_text(json.dumps({'生成时间':now,'修改时间及修改内容':now+'，新边修复与分组改动隔离',
 '文档概述':'保留原第十五轮分组；主文件使用相同受约束末阶段新边收缩',
 '索引目录':['files','changes'],'prior_manifest_sha256':sha(prior_path),
 'contraction_manifest_sha256':sha(here/'288-机器尺度新边受约束收缩源码清单.json'),
 'files':{name:sha(output/name) for name in prior['files']},
 'changes':['恢复第十五轮近共面分组，不按当前角度过滤','单独考察机器尺度新边收缩']},ensure_ascii=False,indent=2)+'\n','utf8')
builder=(here/'289-机器尺度新边原生独立编译.py').read_text('utf8').replace('第十七轮','第十八轮')
(here/'314-原共面分组新边收缩原生独立编译.py').write_text(builder,'utf8')
controller=(here/'290-机器尺度新边编译上传执行.py').read_text('utf8')
for a,b in [('20261006_18','20261006_19'),(current.name,output.name),
 ('288-机器尺度新边受约束收缩源码清单.json',manifest.name),
 ('289-机器尺度新边原生独立编译.py','314-原共面分组新边收缩原生独立编译.py'),
 ('291-机器尺度新边实际编译执行记录.json','316-原共面分组新边收缩实际编译执行记录.json'),
 ('292-机器尺度新边实际编译控制台日志.txt','317-原共面分组新边收缩实际编译控制台日志.txt'),
 ('293-机器尺度新边实际原生编译记录.json','318-原共面分组新边收缩实际原生编译记录.json'),
 ('第十七轮','第十八轮')]:controller=controller.replace(a,b)
(here/'315-原共面分组新边收缩编译上传执行.py').write_text(controller,'utf8')
print('prepared_isolated_contraction_on_prior_grouping')
