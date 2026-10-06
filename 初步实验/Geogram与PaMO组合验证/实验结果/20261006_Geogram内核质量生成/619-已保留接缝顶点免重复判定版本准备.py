"""仅跳过已为真的顶点保留判定，保留标记单调，冻结方法和旧日志不改。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json
import shutil

here=Path(__file__).resolve().parent
folder=here/'第二十四轮已保留接缝顶点免重复判定';folder.mkdir()
frozen=json.loads((here/'569-新边拒绝原生主候选完整开发终态封存清单.json').read_text('utf8'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
for name in ['mesh_surface_intersection.cpp','mesh_surface_intersection_internal.cpp','mesh_surface_intersection_internal.h']:
    p=here/'新边拒绝固定原生候选封存'/name;assert sha(p)==frozen['files'][name];shutil.copy2(p,folder/name)
path=folder/'mesh_surface_intersection_internal.cpp';source=path.read_text('utf8')
anchor='''                v3 = halfedges_.vertex(h,1);
                ExactPoint p1 = I_.exact_vertex(v1);'''
assert source.count(anchor)==1
source=source.replace(anchor,'''                v3 = halfedges_.vertex(h,1);
                // 保留标记只会变为真；已保留顶点无需再次复制准确坐标或判定，前驱仍正常推进。
                if(keep_vertex_[v2]) {
                    v1 = v2;
                    continue;
                }
                ExactPoint p1 = I_.exact_vertex(v1);''')
path.write_text(source,'utf8')
now=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
record={'生成时间':now,'修改时间及修改内容':'首次已保留接缝顶点免重复精确判定开发版',
    '文档概述':'同一轮keep仅false到true；跳过已true顶点的重复判定，区域生成、质量参数及几何规则不变，尚待实际验证',
    '索引目录':['files'],'prior_method_sha256':sha(here/'569-新边拒绝原生主候选完整开发终态封存清单.json'),
    'files':{p.name:sha(p) for p in folder.iterdir() if p.is_file()}}
(here/'620-已保留接缝顶点免重复判定源码清单.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n','utf8')
builder=(here/'509-递归前机器新边拒绝原生独立编译.py').read_text('utf8')
(here/'621-已保留接缝顶点免重复判定独立编译.py').write_text(builder,'utf8')
controller=(here/'510-递归前机器新边拒绝上传编译.py').read_text('utf8')
for old,new in [('20261007_27','20261007_32'),('508-递归前机器新边拒绝版本源码清单','620-已保留接缝顶点免重复判定源码清单'),('第二十二轮递归前机器新边拒绝','第二十四轮已保留接缝顶点免重复判定'),('509-递归前机器新边拒绝原生独立编译','621-已保留接缝顶点免重复判定独立编译'),('511-递归前机器新边拒绝实际编译执行记录','623-已保留接缝顶点免重复判定实际编译记录'),('512-递归前机器新边拒绝实际编译控制台日志','624-已保留接缝顶点免重复判定实际编译日志'),('513-递归前机器新边拒绝实际原生编译记录','625-已保留接缝顶点免重复判定原生构建记录'),('递归前机器新边拒绝_','已保留接缝顶点免重复判定_')]:
    controller=controller.replace(old,new)
(here/'622-已保留接缝顶点免重复判定上传编译.py').write_text(controller,'utf8')
print('prepared_monotone_keep_skip')
