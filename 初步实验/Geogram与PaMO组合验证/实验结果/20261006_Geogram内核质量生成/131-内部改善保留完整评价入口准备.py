"""新候选沿用同输入、同重复与同计时口径，不能覆盖第七轮结果。"""
from pathlib import Path

here=Path(__file__).resolve().parent
worker=(here/'117-有界邻域生成原生交错评价与诊断.py').read_text('utf8').replace('第七轮','第八轮')
(here/'132-内部改善保留原生交错评价与诊断.py').write_text(worker,'utf8')
controller=(here/'118-有界邻域生成实际评价上传执行取回.py').read_text('utf8')
for old,new in [('第七轮','第八轮'),('20261006_08','20261006_09'),
                ('110-有界共边与邻域再生成源码清单.json','125-差面边界触发与内部改善保留源码清单.json'),
                ('115-有界邻域生成实际原生编译记录.json','130-内部改善保留实际原生编译记录.json'),
                ('117-有界邻域生成原生交错评价与诊断.py','132-内部改善保留原生交错评价与诊断.py'),
                ('119-有界邻域生成原生评价执行取回记录.json','134-内部改善保留原生评价执行取回记录.json'),
                ('120-有界邻域生成完整评价控制台日志.txt','135-内部改善保留完整评价控制台日志.txt'),
                ('121-有界邻域生成全部重复与诊断输出.zip','136-内部改善保留全部重复与诊断输出.zip')]:controller=controller.replace(old,new)
(here/'133-内部改善保留实际评价上传执行取回.py').write_text(controller,'utf8')
auditor=(here/'122-有界邻域生成全部重复质量几何速度复算.py').read_text('utf8').replace('第七轮','第八轮')
auditor=auditor.replace('123-有界邻域生成原生十一同输入完整复算.json','138-内部改善保留原生十一同输入完整复算.json')
(here/'137-内部改善保留全部重复质量几何速度复算.py').write_text(auditor,'utf8')
print('新候选完整评价入口已准备')
