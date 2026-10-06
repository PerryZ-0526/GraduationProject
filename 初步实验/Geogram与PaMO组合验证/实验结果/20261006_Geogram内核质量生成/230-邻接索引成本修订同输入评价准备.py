"""只替换当前库绑定，使用相同完整输入、重复次数和评价口径。"""
from pathlib import Path

here=Path(__file__).resolve().parent
worker=(here/'208-免重复生成原生交错评价与有界执行.py').read_text('utf8').replace('第十三轮','第十四轮')
path=here/'231-邻接索引修订原生交错评价与有界执行.py';assert not path.exists();path.write_text(worker,'utf8')
controller=(here/'209-免重复生成原生评价上传执行取回.py').read_text('utf8')
for a,b in [('20261006_14','20261006_15'),
 ('208-免重复生成原生交错评价与有界执行.py',path.name),
 ('206-免重复生成实际原生编译记录.json','229-邻接索引修订实际原生编译记录.json'),
 ('201-整体通过后免重复生成源码清单.json','224-共边邻接索引成本修订源码清单.json'),
 ('210-免重复生成原生评价执行取回记录.json','233-邻接索引修订原生评价执行取回记录.json'),
 ('211-免重复生成原生完整评价控制台日志.txt','234-邻接索引修订原生完整评价控制台日志.txt'),
 ('212-免重复生成原生全部重复与诊断输出.zip','235-邻接索引修订原生全部重复与诊断输出.zip'),
 ('第十三轮免重复生成原生全部重复与诊断输出','第十四轮邻接索引修订原生全部重复与诊断输出'),
 ('第十三轮','第十四轮')]:controller=controller.replace(a,b)
path=here/'232-邻接索引修订原生评价上传执行取回.py';assert not path.exists();path.write_text(controller,'utf8')
code=(here/'214-免重复生成全部重复质量几何速度复算.py').read_text('utf8')
code=code.replace('第十三轮免重复生成原生全部重复与诊断输出','第十四轮邻接索引修订原生全部重复与诊断输出')
code=code.replace('215-免重复生成原生十一同输入完整复算.json','237-邻接索引修订原生十一同输入完整复算.json')
path=here/'236-邻接索引修订全部重复质量几何速度复算.py';assert not path.exists();path.write_text(code,'utf8')
print('prepared_same_input_hash_index_comparison')
