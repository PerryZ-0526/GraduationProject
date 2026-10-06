"""绑定共享边生成实际构建，保留固定十一输入、六次重复和另行轨迹。"""
from pathlib import Path

here=Path(__file__).resolve().parent
worker=(here/'51-第三轮远端原生交错评价与生成诊断.py').read_text('utf8').replace('第三轮','第五轮')
worker=worker.replace("'zero_edge_log':[line for line in p.stdout.splitlines() if 'contracted_zero_length_edges=' in line]}",
''' 'zero_edge_log':[line for line in p.stdout.splitlines() if 'contracted_zero_length_edges=' in line],
            'whole_quality_log':[line for line in p.stdout.splitlines() if 'shared_edges=' in line]}''')
(here/'75-第五轮原生交错评价与共边生成诊断.py').write_text(worker,'utf8')
controller=(here/'52-第三轮实际原生评价上传执行与取回.py').read_text('utf8')
for old,new in [('第三轮','第五轮'),('20261006_04','20261006_06'),
                ('44-第五轮内部顺序与索引修订源码清单.json','68-第五轮共享子边同步源码清单.json'),
                ('49-第五轮实际原生编译记录.json','73-第五轮实际原生编译记录.json'),
                ('51-第五轮远端原生交错评价与生成诊断.py','75-第五轮原生交错评价与共边生成诊断.py'),
                ('53-第五轮原生评价实际执行取回记录.json','77-第五轮原生评价实际执行取回记录.json'),
                ('54-第五轮完整评价控制台日志.txt','78-第五轮完整评价控制台日志.txt'),
                ('55-第五轮全部重复与原生诊断输出.zip','79-第五轮全部重复与共边诊断输出.zip')]:controller=controller.replace(old,new)
(here/'76-第五轮实际原生评价上传执行与取回.py').write_text(controller,'utf8')
auditor=(here/'56-第三轮全部重复质量几何与速度复算.py').read_text('utf8').replace('第三轮','第五轮')
auditor=auditor.replace('57-第五轮原生十一同输入质量几何与速度复算.json','81-第五轮原生十一同输入质量几何与速度复算.json')
(here/'80-第五轮全部重复质量几何与速度复算.py').write_text(auditor,'utf8')
print('第五轮完整评价入口已准备')
