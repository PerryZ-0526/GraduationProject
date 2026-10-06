"""追加真实第四刀准确共面断言输入，完整保留此前十三开发案例。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json

here=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
prior=here/'352-原生十三同输入含自交与超时负例冻结清单.json'
manifest=json.loads(prior.read_text('utf8'))
parent=here/'原生第四刀准确共面断言复用资产/00-真实第三刀有效父网格.obj'
tool=here/'原生第四刀准确共面断言复用资产/01-真实第四刀工具.obj'
scene=json.loads((here/'368-原生第四刀准确共面断言复用资产清单.json').read_text('utf8'))
assert sha(parent)==scene['parent_sha256'] and sha(tool)==scene['tool_sha256']
manifest['cases'].append({'id':'原生CT第四刀准确共面断言负例','kind':'CT连续反馈已见负例',
 'parent':str(parent),'tool':str(tool),'parent_sha256':sha(parent),'tool_sha256':sha(tool)})
now=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
manifest.update(生成时间=now,修改时间及修改内容=now+'，追加原生第四刀准确共面负例',
 文档概述='十四例均已见开发；原十三例不变；完整196调用；不设速度固定验收值',
 prior_manifest_sha256=sha(prior),candidate_source_manifest_sha256=sha(here/'370-共面重建前合法新边清理源码清单.json'))
path=here/'391-原生十四同输入含第四刀断言负例冻结清单.json';assert not path.exists()
path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n','utf8')
worker=(here/'353-逐轮修复原生十三输入完整交错评价.py').read_text('utf8')
worker=worker.replace('第十九轮','第二十轮').replace('原生十三同输入','原生十四同输入')
worker=worker.replace("record['planned_native_benchmark_attempts'] = 182","record['planned_native_benchmark_attempts'] = 196")
(here/'392-共面前清理原生十四输入完整交错评价.py').write_text(worker,'utf8')
controller=(here/'354-逐轮修复十三输入评价上传执行取回.py').read_text('utf8')
for a,b in [('20261006_20','20261006_21'),
 ('352-原生十三同输入含自交与超时负例冻结清单.json',path.name),
 ('336-互斥邻域逐轮新边收缩源码清单.json','370-共面重建前合法新边清理源码清单.json'),
 ('341-逐轮新边收缩实际原生编译记录.json','375-共面重建前清理实际原生编译记录.json'),
 ('353-逐轮修复原生十三输入完整交错评价.py','392-共面前清理原生十四输入完整交错评价.py'),
 ('355-逐轮修复原生十三输入执行取回记录.json','394-共面前清理原生十四输入执行取回记录.json'),
 ('356-逐轮修复原生十三输入完整评价控制台日志.txt','395-共面前清理原生十四输入完整评价控制台日志.txt'),
 ('357-逐轮修复原生十三输入全部输出.zip','396-共面前清理原生十四输入全部输出.zip'),
 ('第十九轮逐轮修复原生十三输入全部输出','第二十轮共面前清理原生十四输入全部输出'),
 ('第十九轮','第二十轮'),('原生十三同输入','原生十四同输入')]:controller=controller.replace(a,b)
assert 'for i in [11,12]:' in controller
controller=controller.replace('for i in [11,12]:','for i in [11,12,13]:')
(here/'393-共面前清理十四输入评价上传执行取回.py').write_text(controller,'utf8')
summary=(here/'358-逐轮修复十三输入全部质量几何速度复算.py').read_text('utf8')
for a,b in [('第十九轮逐轮修复原生十三输入全部输出','第二十轮共面前清理原生十四输入全部输出'),
 ('352-原生十三同输入含自交与超时负例冻结清单.json',path.name),
 ('359-逐轮修复原生十三同输入完整复算.json','398-共面前清理原生十四同输入完整复算.json'),
 ('原生十三同输入','原生十四同输入'),('completed_all_182_saved_quality_recomputations_and_thirteen_geometry_timing_pairs',
 'completed_all_196_saved_quality_recomputations_and_fourteen_geometry_timing_pairs'),
 ("len(summary['all_repeat_quality'])==182 and len(summary['cases'])==13","len(summary['all_repeat_quality'])==196 and len(summary['cases'])==14")]:summary=summary.replace(a,b)
(here/'397-共面前清理十四输入全部质量几何速度复算.py').write_text(summary,'utf8')
audit=(here/'360-十三输入全部182保存重复精确复审.py').read_text('utf8').replace('原生十三同输入','原生十四同输入').replace('182','196')
(here/'399-十四输入全部196保存重复精确复审.py').write_text(audit,'utf8')
controller=(here/'361-全部182保存重复精确复审上传取回.py').read_text('utf8')
for a,b in [('20261006_20','20261006_21'),
 ('360-十三输入全部182保存重复精确复审.py','399-十四输入全部196保存重复精确复审.py'),
 ('362-全部182重复精确复审实际取回记录.json','401-全部196重复精确复审实际取回记录.json'),
 ('363-全部182重复精确复审控制台日志.txt','402-全部196重复精确复审控制台日志.txt'),
 ('364-全部182保存对象精确复审全部输出.zip','403-全部196保存对象精确复审全部输出.zip'),
 ('十三输入全部182保存重复准确复审','十四输入全部196保存重复准确复审'),
 ('01-全部182保存对象准确复审记录.json','01-全部196保存对象准确复审记录.json')]:controller=controller.replace(a,b)
(here/'400-全部196保存重复精确复审上传取回.py').write_text(controller,'utf8')
print('prepared_fourteen_development_cases_all_196_calls')
