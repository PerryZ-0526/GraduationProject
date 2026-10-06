"""追加真实超时父输入，十三个已见开发例完整交错评价，不缩小分母。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json

here=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
now=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
prior=here/'295-原生十二同输入含第二刀负例冻结清单.json'
manifest=json.loads(prior.read_text('utf8'))
parent=here/'新边收缩原生CT十六刀全部实际输出/e00_candidate.obj'
tool=here/'原生CT十六刀开发冻结输入/01_tool.obj'
assert sha(parent)=='288a7552c3680cd9fc809f685a00de67035bb9c10712b1ff77372a9df7c1cdfc'
manifest['cases'].append({'id':'原生CT新父第二刀实际超时负例','kind':'CT连续反馈已见负例',
 'parent':str(parent),'tool':str(tool),'parent_sha256':sha(parent),'tool_sha256':sha(tool)})
manifest.update(生成时间=now,修改时间及修改内容=now+'，追加真实超时同父负例',
 文档概述='十三例全部已见开发输入；预热一测量六；速度标准待完整统计后确定',
 prior_manifest_sha256=sha(prior),candidate_source_manifest_sha256=sha(here/'336-互斥邻域逐轮新边收缩源码清单.json'))
path=here/'352-原生十三同输入含自交与超时负例冻结清单.json';assert not path.exists()
path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n','utf8')
worker=(here/'296-新边收缩原生十二输入交错评价与有界执行.py').read_text('utf8')
worker=worker.replace('第十七轮','第十九轮').replace('原生十二同输入','原生十三同输入')
worker=worker.replace("record['planned_native_benchmark_attempts'] = 168","record['planned_native_benchmark_attempts'] = 182")
(here/'353-逐轮修复原生十三输入完整交错评价.py').write_text(worker,'utf8')
controller=(here/'297-新边收缩十二输入评价上传执行取回.py').read_text('utf8')
for a,b in [('20261006_18','20261006_20'),
 ('295-原生十二同输入含第二刀负例冻结清单.json',path.name),
 ('288-机器尺度新边受约束收缩源码清单.json','336-互斥邻域逐轮新边收缩源码清单.json'),
 ('293-机器尺度新边实际原生编译记录.json','341-逐轮新边收缩实际原生编译记录.json'),
 ('296-新边收缩原生十二输入交错评价与有界执行.py','353-逐轮修复原生十三输入完整交错评价.py'),
 ('298-新边收缩原生十二输入评价执行取回记录.json','355-逐轮修复原生十三输入执行取回记录.json'),
 ('299-新边收缩原生十二输入完整评价控制台日志.txt','356-逐轮修复原生十三输入完整评价控制台日志.txt'),
 ('300-新边收缩原生十二输入全部输出.zip','357-逐轮修复原生十三输入全部输出.zip'),
 ('第十七轮新边收缩原生十二输入全部输出','第十九轮逐轮修复原生十三输入全部输出'),
 ('第十七轮','第十九轮'),('原生十二同输入','原生十三同输入')]:controller=controller.replace(a,b)
old="""        extra=json.loads((here/'352-原生十三同输入含自交与超时负例冻结清单.json').read_text('utf8'))['cases'][11]
        for role in ['parent','tool']:
            source=Path(extra[role]);assert sha(source)==extra[role+'_sha256']
            sftp.put(str(source),root+'/inputs/11_'+role+'.obj')"""
new="""        inputs=json.loads((here/'352-原生十三同输入含自交与超时负例冻结清单.json').read_text('utf8'))['cases']
        for i in [11,12]:
            for role in ['parent','tool']:
                source=Path(inputs[i][role]);assert sha(source)==inputs[i][role+'_sha256']
                sftp.put(str(source),root+'/inputs/'+str(i)+'_'+role+'.obj')"""
assert old in controller;controller=controller.replace(old,new)
(here/'354-逐轮修复十三输入评价上传执行取回.py').write_text(controller,'utf8')
summary=(here/'301-新边收缩十二输入全部重复质量几何速度复算.py').read_text('utf8')
for a,b in [('第十七轮新边收缩原生十二输入全部输出','第十九轮逐轮修复原生十三输入全部输出'),
 ('295-原生十二同输入含第二刀负例冻结清单.json',path.name),
 ('302-新边收缩原生十二同输入完整复算.json','359-逐轮修复原生十三同输入完整复算.json'),
 ('原生十二同输入','原生十三同输入'),('completed_all_168_saved_quality_recomputations_and_twelve_geometry_timing_pairs',
 'completed_all_182_saved_quality_recomputations_and_thirteen_geometry_timing_pairs'),
 ("len(summary['all_repeat_quality'])==168 and len(summary['cases'])==12","len(summary['all_repeat_quality'])==182 and len(summary['cases'])==13")]:summary=summary.replace(a,b)
(here/'358-逐轮修复十三输入全部质量几何速度复算.py').write_text(summary,'utf8')
audit=(here/'328-十二输入全部重复同保存对象精确复审.py').read_text('utf8').replace('原生十二同输入','原生十三同输入').replace('168','182')
(here/'360-十三输入全部182保存重复精确复审.py').write_text(audit,'utf8')
controller=(here/'329-全部重复精确复审上传执行取回.py').read_text('utf8')
for a,b in [('20261006_18','20261006_20'),
 ('328-十二输入全部重复同保存对象精确复审.py','360-十三输入全部182保存重复精确复审.py'),
 ('330-全部重复精确复审实际执行取回记录.json','362-全部182重复精确复审实际取回记录.json'),
 ('331-全部重复精确复审实际控制台日志.txt','363-全部182重复精确复审控制台日志.txt'),
 ('332-全部168保存对象精确复审全部输出.zip','364-全部182保存对象精确复审全部输出.zip'),
 ('十二输入全部168保存重复准确复审','十三输入全部182保存重复准确复审'),
 ('01-全部168保存对象准确复审记录.json','01-全部182保存对象准确复审记录.json')]:controller=controller.replace(a,b)
(here/'361-全部182保存重复精确复审上传取回.py').write_text(controller,'utf8')
print('prepared_thirteen_seen_inputs_all_182_native_calls_and_exact_audit')
