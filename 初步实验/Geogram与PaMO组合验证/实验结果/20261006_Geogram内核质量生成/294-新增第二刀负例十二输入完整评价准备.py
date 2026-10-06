"""将真实第二刀负例加入原生开发回归；完整保留原十一例和全部重复。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json

here=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
now=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
old_manifest=here/'18-原生十一同输入开发与速度运行前清单.json'
manifest=json.loads(old_manifest.read_text('utf8'))
parent=here/'原生CT十六刀反馈全部实际输出/e00_candidate.obj'
tool=here/'原生CT十六刀开发冻结输入/01_tool.obj'
assert sha(parent)=='8d5590f6e8f55f5b24007da3ae13b583f9d59622ed86a8a53a919ec607abb318'
assert sha(tool)=='969b169e548770eccd368d6b6c33c6196a49bc4ecd76c853977225335cb8ab8d'
manifest.update(生成时间=now,修改时间及修改内容=now+'，追加第二刀已见自交负例',
 文档概述='十二例全部为已见开发输入；原十一例不变；速度标准由完整统计后确定',
 prior_manifest_sha256=sha(old_manifest),candidate_source_manifest_sha256=sha(here/'288-机器尺度新边受约束收缩源码清单.json'))
manifest['cases'].append({'id':'原生CT第二刀机器尺度新边自交负例','kind':'CT连续反馈已见负例',
 'parent':str(parent),'tool':str(tool),'parent_sha256':sha(parent),'tool_sha256':sha(tool)})
path=here/'295-原生十二同输入含第二刀负例冻结清单.json';assert not path.exists()
path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n','utf8')
worker=(here/'272-当前差面分组原生交错评价与有界执行.py').read_text('utf8')
worker=worker.replace('第十六轮','第十七轮').replace('原生十一同输入','原生十二同输入')
worker=worker.replace("record['planned_native_benchmark_attempts'] = 154","record['planned_native_benchmark_attempts'] = 168")
(here/'296-新边收缩原生十二输入交错评价与有界执行.py').write_text(worker,'utf8')
controller=(here/'273-当前差面分组原生评价上传执行取回.py').read_text('utf8')
for a,b in [('20261006_17','20261006_18'),
 ('18-原生十一同输入开发与速度运行前清单.json',path.name),
 ('265-当前差面触发近共面分组源码清单.json','288-机器尺度新边受约束收缩源码清单.json'),
 ('270-当前差面分组实际原生编译记录.json','293-机器尺度新边实际原生编译记录.json'),
 ('272-当前差面分组原生交错评价与有界执行.py','296-新边收缩原生十二输入交错评价与有界执行.py'),
 ('274-当前差面分组原生评价执行取回记录.json','298-新边收缩原生十二输入评价执行取回记录.json'),
 ('275-当前差面分组原生完整评价控制台日志.txt','299-新边收缩原生十二输入完整评价控制台日志.txt'),
 ('276-当前差面分组原生全部重复与诊断输出.zip','300-新边收缩原生十二输入全部输出.zip'),
 ('第十六轮当前差面分组原生全部重复与诊断输出','第十七轮新边收缩原生十二输入全部输出'),
 ('第十六轮','第十七轮'),('原生十一同输入','原生十二同输入')]:controller=controller.replace(a,b)
marker="        sftp.put(str(here/'295-原生十二同输入含第二刀负例冻结清单.json'),root+'/native_inputs.json')"
assert marker in controller
controller=controller.replace(marker,"""        # 新增负例仅写入本轮真实输入目录，不碰旧软链接及历史冻结文件。
        extra=json.loads((here/'295-原生十二同输入含第二刀负例冻结清单.json').read_text('utf8'))['cases'][11]
        for role in ['parent','tool']:
            source=Path(extra[role]);assert sha(source)==extra[role+'_sha256']
            sftp.put(str(source),root+'/inputs/11_'+role+'.obj')
"""+marker)
(here/'297-新边收缩十二输入评价上传执行取回.py').write_text(controller,'utf8')
code=(here/'277-当前差面分组全部重复质量几何速度复算.py').read_text('utf8')
for a,b in [('第十六轮当前差面分组原生全部重复与诊断输出','第十七轮新边收缩原生十二输入全部输出'),
 ('18-原生十一同输入开发与速度运行前清单.json',path.name),
 ('278-当前差面分组原生十一同输入完整复算.json','302-新边收缩原生十二同输入完整复算.json'),
 ('原生十一同输入','原生十二同输入'),('completed_all_154_saved_quality_recomputations_and_eleven_geometry_timing_pairs',
 'completed_all_168_saved_quality_recomputations_and_twelve_geometry_timing_pairs'),
 ("len(summary['all_repeat_quality'])==154 and len(summary['cases'])==11", "len(summary['all_repeat_quality'])==168 and len(summary['cases'])==12")]:code=code.replace(a,b)
(here/'301-新边收缩十二输入全部重复质量几何速度复算.py').write_text(code,'utf8')
print('prepared_twelve_seen_native_development_inputs_168_calls')
