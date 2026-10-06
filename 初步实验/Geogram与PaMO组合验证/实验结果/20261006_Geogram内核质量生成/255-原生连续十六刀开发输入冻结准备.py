"""复制既有CT16初态和工具，原生父链从初态开始，不复用旧维护输出。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json
import shutil

here=Path(__file__).resolve().parent
prior_path=Path('D:/GraduationProject_切削排斥证据/20261006_Geogram自适应局部质量真实CT连续验证/43-自适应局部质量真实CT十六刀冻结清单.json')
prior=json.loads(prior_path.read_text('utf8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
folder=here/'原生CT十六刀开发冻结输入';folder.mkdir()
initial=Path(prior['initial']);assert sha(initial)==prior['initial_sha256']
shutil.copy2(initial,folder/'00_initial.obj')
tools=[]
for i,tool in enumerate(prior['tools']):
    source=Path(tool['path']);assert sha(source)==tool['sha256']
    name=f'{i:02d}_tool.obj';shutil.copy2(source,folder/name)
    tools.append({'event_index':i,'event_id':tool['event_id'],'file':name,'sha256':sha(folder/name)})
assert len(tools)==16
now=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
record={'生成时间':now,'修改时间及修改内容':now+'，首次冻结原生反馈开发路线',
        '文档概述':'既有已见CT路线；同一次候选父输入分别作原版和候选，不混为原版独立反馈链',
        '索引目录':['initial','tools','evaluation_scope'],'source_manifest_sha256':sha(prior_path),
        'initial':{'file':'00_initial.obj','sha256':sha(folder/'00_initial.obj')},'tools':tools,
        'evaluation_scope':'seen_development_native_candidate_feedback_with_same_parent_original_controls',
        'candidate_manifest_sha256':sha(here/'241-共边受影响区域限定再生成源码清单.json'),
        'candidate_build_sha256':sha(here/'246-受影响区域限定实际原生编译记录.json')}
path=here/'256-原生CT十六刀反馈开发冻结清单.json';assert not path.exists()
path.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n','utf8')
print('frozen_original_initial_and_sixteen_tools_for_new_native_parent_chain')
