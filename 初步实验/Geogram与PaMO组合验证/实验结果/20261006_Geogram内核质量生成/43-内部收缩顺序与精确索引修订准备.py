"""保留第二轮源码，在新版本中修正收缩顺序及压缩后的精确点索引。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json

here=Path(__file__).resolve().parent
source=here/'第二轮零位移收缩与生成诊断'
output=here/'第三轮收缩顺序与精确索引修订'
output.mkdir()
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
prior=json.loads((here/'36-第二轮零位移收缩与生成诊断源码清单.json').read_text('utf8'))
for name,digest in prior['files'].items():
    assert sha(source/name)==digest
    (output/name).write_bytes((source/name).read_bytes())
path=output/'mesh_surface_intersection.cpp'
main=path.read_text('utf8')
old='''        // 分类完成后处理双精度表示中的零长度边，不重写原版准确交点表。
        contract_collapsed_float_edges(result);'''
assert main.count(old)==1
main=main.replace(old,'')
old='''\t    I.simplify_coplanar_facets();
\t}
    }

    void mesh_remove_intersections'''
new='''\t    I.simplify_coplanar_facets();
\t}
        // 所有准确交点查询完成后再收缩零长度边，避免中途重排顶点编号。
        contract_collapsed_float_edges(result);
    }

    void mesh_remove_intersections'''
assert main.count(old)==1
main=main.replace(old,new)
old='''        if(!inserted) {
            return it->second;
        }
        vec3 p_inexact = PCK::approximate(p);'''
new='''        // 已删除顶点对应的准确点仍保留键；只有当前有效编号才能直接复用。
        if(!inserted && it->second != NO_INDEX) {
            return it->second;
        }
        vec3 p_inexact = PCK::approximate(p);'''
assert main.count(old)==1
main=main.replace(old,new)
old='''\tStopwatch W("Coplanar",verbose_);
        Attribute<index_t> facet_group'''
new='''\tStopwatch W("Coplanar",verbose_);
        // 分类删除面时可能压缩顶点；按随顶点迁移的准确点属性重建当前编号。
        for(auto& point : exact_point_to_vertex_) point.second = NO_INDEX;
        for(index_t v : mesh_.vertices) {
            if(vertex_to_exact_point_[v] != nullptr) {
                auto point = exact_point_to_vertex_.find(*vertex_to_exact_point_[v]);
                geo_assert(point != exact_point_to_vertex_.end());
                point->second = v;
            }
        }
        Attribute<index_t> facet_group'''
assert main.count(old)==1
main=main.replace(old,new)
path.write_text(main,'utf8')
record={'生成时间':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),
        '修改时间及修改内容':'零长度边收缩移至准确操作之后；重建压缩后的交点编号并区分已删除点',
        '文档概述':'第三轮原生代码版本；第二轮源码、构建及历史结果保持',
        '索引目录':['files'],'status':'prepared_third_native_index_and_order_revision',
        'prior_manifest_sha256':sha(here/'36-第二轮零位移收缩与生成诊断源码清单.json'),
        'files':{p.name:sha(p) for p in output.iterdir()},'quality_options':'rpzq20YYS64Q',
        'trace_enabled_in_timed_benchmark':False}
(here/'44-第三轮内部顺序与索引修订源码清单.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n','utf8')
# 构建仍从冻结首轮复制，只覆盖本版三份生成代码，原版基线逐字节复用。
builder=(here/'38-第二轮原生内核独立编译.py').read_text('utf8').replace('第二轮','第三轮')
(here/'45-第三轮原生内核独立编译.py').write_text(builder,'utf8')
controller=(here/'39-第二轮隔离编译上传与执行.py').read_text('utf8')
for old,new in [('第二轮','第三轮'),('20261006_03','20261006_04'),
                ('36-第三轮零位移收缩与生成诊断源码清单.json','44-第三轮内部顺序与索引修订源码清单.json'),
                ('第三轮零位移收缩与生成诊断','第三轮收缩顺序与精确索引修订'),
                ('38-第三轮原生内核独立编译.py','45-第三轮原生内核独立编译.py'),
                ('40-第三轮实际编译执行记录.json','47-第三轮实际编译执行记录.json'),
                ('41-第三轮实际编译控制台日志.txt','48-第三轮实际编译控制台日志.txt'),
                ('42-第三轮实际原生编译记录.json','49-第三轮实际原生编译记录.json')]:
    controller=controller.replace(old,new)
(here/'46-第三轮隔离编译上传与执行.py').write_text(controller,'utf8')
print('第三轮修订源码及实际构建入口已准备')
