"""保留第四轮实际失败，修正GEO容器初始化并补全两侧已分段边的同步。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json

here=Path(__file__).resolve().parent
source=here/'第四轮准确共享边补点生成'
output=here/'第五轮共享子边同步生成';output.mkdir()
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
prior=json.loads((here/'60-第四轮准确共享边生成源码清单.json').read_text('utf8'))
for name,digest in prior['files'].items():
    assert sha(source/name)==digest
    (output/name).write_bytes((source/name).read_bytes())
main=(output/'mesh_surface_intersection.cpp').read_text('utf8')
old=(here/'58-共享边补点一致提交与整体质量检查.cpp').read_text('utf8')
end=old.index('struct NativeQualityScore')
assert main.count(old[:end])==1
main=main.replace(old[:end],(here/'66-共享边子段双侧补点同步.cpp').read_text('utf8')+'\n')
(output/'mesh_surface_intersection.cpp').write_text(main,'utf8')
path=output/'mesh_surface_intersection_internal.cpp';internal=path.read_text('utf8')
old='        std::set<int> visited;vector<int> stack={a};'
assert internal.count(old)==1
internal=internal.replace(old,'        // GEO容器不接受该单元素初始化列表，显式压入链端点。\n        std::set<int> visited;vector<int> stack;stack.push_back(a);')
path.write_text(internal,'utf8')
record={'生成时间':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),
        '修改时间及修改内容':'修正实际编译失败及双侧已细分边链的同步遗漏',
        '文档概述':'第五轮独立原生源码；不覆盖第四轮失败记录',
        '索引目录':['files'],'status':'prepared_fifth_native_shared_subedge_generation',
        'prior_manifest_sha256':sha(here/'60-第四轮准确共享边生成源码清单.json'),
        'files':{p.name:sha(p) for p in output.iterdir()},'quality_options':'rpzq20S64Q'}
(here/'68-第五轮共享子边同步源码清单.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n','utf8')
builder=(here/'61-第四轮原生内核独立编译.py').read_text('utf8').replace('第四轮','第五轮')
(here/'69-第五轮原生内核独立编译.py').write_text(builder,'utf8')
controller=(here/'62-第四轮隔离编译上传与执行.py').read_text('utf8')
for old,new in [('第四轮','第五轮'),('20261006_05','20261006_06'),
                ('60-第五轮准确共享边生成源码清单.json','68-第五轮共享子边同步源码清单.json'),
                ('第五轮准确共享边补点生成','第五轮共享子边同步生成'),
                ('61-第五轮原生内核独立编译.py','69-第五轮原生内核独立编译.py'),
                ('63-第五轮实际编译执行记录.json','71-第五轮实际编译执行记录.json'),
                ('64-第五轮实际编译控制台日志.txt','72-第五轮实际编译控制台日志.txt'),
                ('65-第五轮实际原生编译记录.json','73-第五轮实际原生编译记录.json')]:controller=controller.replace(old,new)
(here/'70-第五轮隔离编译上传与执行.py').write_text(controller,'utf8')
print('第五轮共享子边同步修订已准备')
