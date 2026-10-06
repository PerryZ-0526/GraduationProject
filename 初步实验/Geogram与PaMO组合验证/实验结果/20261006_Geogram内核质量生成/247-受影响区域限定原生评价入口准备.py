"""复用完整十一输入评价，只绑定已经冻结的区域限定新版本。"""
from pathlib import Path

here=Path(__file__).resolve().parent
worker=(here/'231-邻接索引修订原生交错评价与有界执行.py').read_text('utf8').replace('第十四轮','第十五轮')
path=here/'248-受影响区域限定原生交错评价与有界执行.py';assert not path.exists();path.write_text(worker,'utf8')
controller=(here/'232-邻接索引修订原生评价上传执行取回.py').read_text('utf8')
for a,b in [('20261006_15','20261006_16'),
 ('231-邻接索引修订原生交错评价与有界执行.py',path.name),
 ('229-邻接索引修订实际原生编译记录.json','246-受影响区域限定实际原生编译记录.json'),
 ('224-共边邻接索引成本修订源码清单.json','241-共边受影响区域限定再生成源码清单.json'),
 ('233-邻接索引修订原生评价执行取回记录.json','250-受影响区域限定原生评价执行取回记录.json'),
 ('234-邻接索引修订原生完整评价控制台日志.txt','251-受影响区域限定原生完整评价控制台日志.txt'),
 ('235-邻接索引修订原生全部重复与诊断输出.zip','252-受影响区域限定原生全部重复与诊断输出.zip'),
 ('第十四轮邻接索引修订原生全部重复与诊断输出','第十五轮受影响区域限定原生全部重复与诊断输出'),
 ('第十四轮','第十五轮')]:controller=controller.replace(a,b)
path=here/'249-受影响区域限定原生评价上传执行取回.py';assert not path.exists();path.write_text(controller,'utf8')
code=(here/'236-邻接索引修订全部重复质量几何速度复算.py').read_text('utf8')
code=code.replace('第十四轮邻接索引修订原生全部重复与诊断输出','第十五轮受影响区域限定原生全部重复与诊断输出')
code=code.replace('237-邻接索引修订原生十一同输入完整复算.json','254-受影响区域限定原生十一同输入完整复算.json')
path=here/'253-受影响区域限定全部重复质量几何速度复算.py';assert not path.exists();path.write_text(code,'utf8')
print('prepared_complete_native_evaluation_for_affected_groups')
