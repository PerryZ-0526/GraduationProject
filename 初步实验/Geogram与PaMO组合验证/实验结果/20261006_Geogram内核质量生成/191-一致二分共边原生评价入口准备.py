"""绑定一致二分条带新版本，旧方法和旧输出保持不变。"""
from pathlib import Path

here=Path(__file__).resolve().parent
worker=(here/'161-种子组原生交错评价与有界执行.py').read_text('utf8').replace('第十轮','第十二轮')
path=here/'192-一致二分共边原生交错评价与有界执行.py';assert not path.exists();path.write_text(worker,'utf8')
controller=(here/'162-种子组原生评价上传执行取回.py').read_text('utf8')
for a,b in [('20261006_11','20261006_13'),
 ('161-种子组原生交错评价与有界执行.py',path.name),
 ('159-种子分组与边界一致实际原生编译记录.json','190-一致二分共边实际原生编译记录.json'),
 ('154-种子分组与边界一致生成源码清单.json','185-一致二分共边条带生成源码清单.json'),
 ('163-种子组原生评价执行取回记录.json','194-一致二分共边原生评价执行取回记录.json'),
 ('164-种子组原生完整评价控制台日志.txt','195-一致二分共边原生完整评价控制台日志.txt'),
 ('165-种子组原生全部重复与诊断输出.zip','196-一致二分共边原生全部重复与诊断输出.zip'),
 ('第十轮种子组原生全部重复与诊断输出','第十二轮一致二分共边原生全部重复与诊断输出'),
 ('第十轮','第十二轮')]:controller=controller.replace(a,b)
path=here/'193-一致二分共边原生评价上传执行取回.py';assert not path.exists();path.write_text(controller,'utf8')
code=(here/'169-种子组全部重复质量几何速度复算.py').read_text('utf8')
code=code.replace('第十轮种子组原生全部重复与诊断输出','第十二轮一致二分共边原生全部重复与诊断输出')
code=code.replace('170-种子组原生十一同输入完整复算.json','199-一致二分共边原生十一同输入完整复算.json')
path=here/'198-一致二分共边全部重复质量几何速度复算.py';assert not path.exists();path.write_text(code,'utf8')
print('prepared_fixed_eleven_input_native_evaluation_and_recomputation')
