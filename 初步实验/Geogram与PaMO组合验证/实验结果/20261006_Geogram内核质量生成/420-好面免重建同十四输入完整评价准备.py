"""复用同一十四开发输入，只绑定好面完整组免重建版本。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json

here=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
prior=here/'391-原生十四同输入含第四刀断言负例冻结清单.json'
manifest=json.loads(prior.read_text('utf8'))
now=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
manifest.update(生成时间=now,修改时间及修改内容=now+'，仅更换候选源码，全部参数和输入不变',
 prior_manifest_sha256=sha(prior),candidate_source_manifest_sha256=sha(here/'405-已有好面完整区域免重建源码清单.json'))
path=here/'421-好面免重建原生十四同输入冻结清单.json';assert not path.exists()
path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n','utf8')
worker=(here/'392-共面前清理原生十四输入完整交错评价.py').read_text('utf8').replace('第二十轮','第二十一轮')
(here/'422-好面免重建原生十四输入完整交错评价.py').write_text(worker,'utf8')
controller=(here/'393-共面前清理十四输入评价上传执行取回.py').read_text('utf8')
for a,b in [('20261006_21','20261007_22'),
 ('391-原生十四同输入含第四刀断言负例冻结清单.json',path.name),
 ('370-共面重建前合法新边清理源码清单.json','405-已有好面完整区域免重建源码清单.json'),
 ('375-共面重建前清理实际原生编译记录.json','410-好面区域免重建实际原生编译记录.json'),
 ('392-共面前清理原生十四输入完整交错评价.py','422-好面免重建原生十四输入完整交错评价.py'),
 ('394-共面前清理原生十四输入执行取回记录.json','424-好面免重建原生十四输入执行取回记录.json'),
 ('395-共面前清理原生十四输入完整评价控制台日志.txt','425-好面免重建原生十四输入完整评价控制台日志.txt'),
 ('396-共面前清理原生十四输入全部输出.zip','426-好面免重建原生十四输入全部输出.zip'),
 ('第二十轮共面前清理原生十四输入全部输出','第二十一轮好面免重建原生十四输入全部输出'),
 ('第二十轮','第二十一轮')]:controller=controller.replace(a,b)
(here/'423-好面免重建十四输入评价上传执行取回.py').write_text(controller,'utf8')
summary=(here/'397-共面前清理十四输入全部质量几何速度复算.py').read_text('utf8')
for a,b in [('第二十轮共面前清理原生十四输入全部输出','第二十一轮好面免重建原生十四输入全部输出'),
 ('391-原生十四同输入含第四刀断言负例冻结清单.json',path.name),
 ('398-共面前清理原生十四同输入完整复算.json','428-好面免重建原生十四同输入完整复算.json')]:summary=summary.replace(a,b)
(here/'427-好面免重建十四输入全部质量几何速度复算.py').write_text(summary,'utf8')
(here/'429-好面免重建全部196保存重复精确复审.py').write_bytes((here/'399-十四输入全部196保存重复精确复审.py').read_bytes())
controller=(here/'400-全部196保存重复精确复审上传取回.py').read_text('utf8')
for a,b in [('20261006_21','20261007_22'),
 ('399-十四输入全部196保存重复精确复审.py','429-好面免重建全部196保存重复精确复审.py'),
 ('401-全部196重复精确复审实际取回记录.json','431-好面免重建全部196重复精确复审取回记录.json'),
 ('402-全部196重复精确复审控制台日志.txt','432-好面免重建全部196重复精确复审控制台日志.txt'),
 ('403-全部196保存对象精确复审全部输出.zip','433-好面免重建全部196保存对象精确复审输出.zip'),
 ('十四输入全部196保存重复准确复审','好面免重建十四输入全部196保存重复准确复审')]:controller=controller.replace(a,b)
(here/'430-好面免重建全部196保存重复精确复审上传取回.py').write_text(controller,'utf8')
print('prepared_same_fourteen_inputs_zero_bad_group_optimization')
