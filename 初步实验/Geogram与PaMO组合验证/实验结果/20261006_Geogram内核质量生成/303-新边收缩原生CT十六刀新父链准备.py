"""绑定新构建与原始十六刀输入，从初态重跑，不能拼接旧发布帧。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json

here=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
now=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
old=here/'256-原生CT十六刀反馈开发冻结清单.json'
manifest=json.loads(old.read_text('utf8'))
build=here/'293-机器尺度新边实际原生编译记录.json'
assert json.loads(build.read_text('utf8'))['status']=='completed_candidate_build_with_verified_original_baseline_reuse'
manifest.update(生成时间=now,修改时间及修改内容=now+'，仅更换冻结实际原生构建，从原初态运行',
 prior_manifest_sha256=sha(old),candidate_build_sha256=sha(build),
 candidate_manifest_sha256=sha(here/'288-机器尺度新边受约束收缩源码清单.json'))
path=here/'304-新边收缩原生CT十六刀新父链冻结清单.json';assert not path.exists()
path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n','utf8')
(here/'305-新边收缩原生CT十六刀候选反馈与同父参照.py').write_bytes((here/'257-原生CT十六刀候选反馈与同父参照.py').read_bytes())
controller=(here/'258-原生CT十六刀反馈实际上传取回.py').read_text('utf8')
for a,b in [('20261006_16','20261006_18'),
 ('256-原生CT十六刀反馈开发冻结清单.json',path.name),
 ('257-原生CT十六刀候选反馈与同父参照.py','305-新边收缩原生CT十六刀候选反馈与同父参照.py'),
 ('259-原生CT十六刀反馈实际执行取回记录.json','307-新边收缩原生CT十六刀实际执行取回记录.json'),
 ('260-原生CT十六刀反馈实际控制台日志.txt','308-新边收缩原生CT十六刀实际控制台日志.txt'),
 ('261-原生CT十六刀反馈全部实际输出.zip','309-新边收缩原生CT十六刀全部实际输出.zip'),
 ("output=here/'原生CT十六刀反馈全部实际输出'","output=here/'新边收缩原生CT十六刀全部实际输出'")]:controller=controller.replace(a,b)
(here/'306-新边收缩原生CT十六刀反馈上传执行取回.py').write_text(controller,'utf8')
print('prepared_actual_new_build_sixteen_events_from_original_initial')
