"""准备免重复生成的完整实际评价与独立复算，所有旧记录保持。"""
from pathlib import Path

here=Path(__file__).resolve().parent
worker=(here/'192-一致二分共边原生交错评价与有界执行.py').read_text('utf8').replace('第十二轮','第十三轮')
path=here/'208-免重复生成原生交错评价与有界执行.py';assert not path.exists();path.write_text(worker,'utf8')
controller=(here/'193-一致二分共边原生评价上传执行取回.py').read_text('utf8')
for a,b in [('20261006_13','20261006_14'),
 ('192-一致二分共边原生交错评价与有界执行.py',path.name),
 ('190-一致二分共边实际原生编译记录.json','206-免重复生成实际原生编译记录.json'),
 ('185-一致二分共边条带生成源码清单.json','201-整体通过后免重复生成源码清单.json'),
 ('194-一致二分共边原生评价执行取回记录.json','210-免重复生成原生评价执行取回记录.json'),
 ('195-一致二分共边原生完整评价控制台日志.txt','211-免重复生成原生完整评价控制台日志.txt'),
 ('196-一致二分共边原生全部重复与诊断输出.zip','212-免重复生成原生全部重复与诊断输出.zip'),
 ('第十二轮一致二分共边原生全部重复与诊断输出','第十三轮免重复生成原生全部重复与诊断输出'),
 ('第十二轮','第十三轮')]:controller=controller.replace(a,b)
path=here/'209-免重复生成原生评价上传执行取回.py';assert not path.exists();path.write_text(controller,'utf8')
code=(here/'169-种子组全部重复质量几何速度复算.py').read_text('utf8')
code=code.replace('第十轮种子组原生全部重复与诊断输出','第十三轮免重复生成原生全部重复与诊断输出')
code=code.replace('170-种子组原生十一同输入完整复算.json','215-免重复生成原生十一同输入完整复算.json')
path=here/'214-免重复生成全部重复质量几何速度复算.py';assert not path.exists();path.write_text(code,'utf8')
print('prepared_native_pair_with_unmodified_quality_gate')
