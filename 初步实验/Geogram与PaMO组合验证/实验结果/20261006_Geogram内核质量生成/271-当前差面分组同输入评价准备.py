"""绑定新增分组质量触发版本，重复次数与完整输入不改变。"""
from pathlib import Path

here=Path(__file__).resolve().parent
worker=(here/'248-受影响区域限定原生交错评价与有界执行.py').read_text('utf8').replace('第十五轮','第十六轮')
path=here/'272-当前差面分组原生交错评价与有界执行.py';assert not path.exists();path.write_text(worker,'utf8')
controller=(here/'249-受影响区域限定原生评价上传执行取回.py').read_text('utf8')
for a,b in [('20261006_16','20261006_17'),
 ('248-受影响区域限定原生交错评价与有界执行.py',path.name),
 ('246-受影响区域限定实际原生编译记录.json','270-当前差面分组实际原生编译记录.json'),
 ('241-共边受影响区域限定再生成源码清单.json','265-当前差面触发近共面分组源码清单.json'),
 ('250-受影响区域限定原生评价执行取回记录.json','274-当前差面分组原生评价执行取回记录.json'),
 ('251-受影响区域限定原生完整评价控制台日志.txt','275-当前差面分组原生完整评价控制台日志.txt'),
 ('252-受影响区域限定原生全部重复与诊断输出.zip','276-当前差面分组原生全部重复与诊断输出.zip'),
 ('第十五轮受影响区域限定原生全部重复与诊断输出','第十六轮当前差面分组原生全部重复与诊断输出'),
 ('第十五轮','第十六轮')]:controller=controller.replace(a,b)
path=here/'273-当前差面分组原生评价上传执行取回.py';assert not path.exists();path.write_text(controller,'utf8')
code=(here/'253-受影响区域限定全部重复质量几何速度复算.py').read_text('utf8')
code=code.replace('第十五轮受影响区域限定原生全部重复与诊断输出','第十六轮当前差面分组原生全部重复与诊断输出')
code=code.replace('254-受影响区域限定原生十一同输入完整复算.json','278-当前差面分组原生十一同输入完整复算.json')
path=here/'277-当前差面分组全部重复质量几何速度复算.py';assert not path.exists();path.write_text(code,'utf8')
print('prepared_current_quality_trigger_native_pair')
