"""冻结九既有原始输入及两份真实CT父输入，区别维护输入与布尔父输入。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json

here=Path(__file__).resolve().parent
path=Path('D:/GraduationProject_切削排斥证据/20261006_自适应局部质量未见参数与同源PaMO对照/05-新参数与同源对照运行前冻结清单.json')
source=json.loads(path.read_text('utf8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
cases=[{k:c[k] for k in ['id','kind','parent','parent_sha256','tool','tool_sha256']} for c in source['cases'][:9]]
study=Path('D:/GraduationProject_切削排斥证据/20261006_Geogram自适应局部质量真实CT连续验证')
mp=study/'43-自适应局部质量真实CT十六刀冻结清单.json'
m=json.loads(mp.read_text('utf8'))
rp=study/'真实CT完整父反馈结果/01-真实CT十六刀完整父反馈记录.json'
r=json.loads(rp.read_text('utf8'))
event=r['routes'][0]['events'][15]
for index,parent,parent_sha in [(0,m['initial'],m['initial_sha256']), (15,event['parent_path'],event['parent_sha256'])]:
    tool=m['tools'][index]
    cases.append({'id':f'既有真实CT原始父输入_{index:02d}','kind':'CT控制','parent':parent,'parent_sha256':parent_sha,
                  'tool':tool['path'],'tool_sha256':tool['sha256']})
for case in cases:
    for key in ['parent','tool']: assert sha(case[key])==case[key+'_sha256']
d={'生成时间':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),
   '修改时间及修改内容':'首次冻结原生生成阶段十一同输入开发案例与交错速度测量',
   '文档概述':'既有开发输入；不能称未见评价；不混入已经切削的维护源网格',
   '索引目录':['cases','benchmark'],'status':'prepared_native_same_input_development',
   'source_manifest_sha256':sha(path),'CT_manifest_sha256':sha(mp),'CT_record_sha256':sha(rp),
   'candidate_source_manifest_sha256':sha(here/'10-隔离内核候选源码准备清单.json'), 'cases':cases,
   'benchmark':{'repeats_per_method_per_case':6,'random_seed':2026100601,
                'cpu_affinity_logical_processors':4,'warmups_per_method_per_case':1,
                'timing_scope':'native_mesh_boolean_operation_load_and_save_reported_separately',
                'all_repeat_outputs_saved':True,'structural_checks_outside_timed_boolean':True}}
(here/'18-原生十一同输入开发与速度运行前清单.json').write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n','utf8')
print('十一实际布尔父输入已绑定',flush=True)
