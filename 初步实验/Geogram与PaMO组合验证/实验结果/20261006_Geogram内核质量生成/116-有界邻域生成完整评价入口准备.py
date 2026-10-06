"""对新内核保持相同固定输入、重复与原生计时口径，完整保存所有尝试。"""
from pathlib import Path

here=Path(__file__).resolve().parent
worker=(here/'75-第五轮原生交错评价与共边生成诊断.py').read_text('utf8').replace('第五轮','第七轮')
(here/'117-有界邻域生成原生交错评价与诊断.py').write_text(worker,'utf8')
controller=(here/'76-第五轮实际原生评价上传执行与取回.py').read_text('utf8')
for old,new in [('第五轮','第七轮'),('20261006_06','20261006_08'),
                ('68-第七轮共享子边同步源码清单.json','110-有界共边与邻域再生成源码清单.json'),
                ('73-第七轮实际原生编译记录.json','115-有界邻域生成实际原生编译记录.json'),
                ('75-第七轮原生交错评价与共边生成诊断.py','117-有界邻域生成原生交错评价与诊断.py'),
                ('77-第七轮原生评价实际执行取回记录.json','119-有界邻域生成原生评价执行取回记录.json'),
                ('78-第七轮完整评价控制台日志.txt','120-有界邻域生成完整评价控制台日志.txt'),
                ('79-第七轮全部重复与共边诊断输出.zip','121-有界邻域生成全部重复与诊断输出.zip')]:controller=controller.replace(old,new)
(here/'118-有界邻域生成实际评价上传执行取回.py').write_text(controller,'utf8')
auditor=(here/'80-第五轮全部重复质量几何与速度复算.py').read_text('utf8').replace('第五轮','第七轮')
auditor=auditor.replace('81-第七轮原生十一同输入质量几何与速度复算.json','123-有界邻域生成原生十一同输入完整复算.json')
(here/'122-有界邻域生成全部重复质量几何速度复算.py').write_text(auditor,'utf8')
print('新内核固定十一输入完整评价入口已准备')
