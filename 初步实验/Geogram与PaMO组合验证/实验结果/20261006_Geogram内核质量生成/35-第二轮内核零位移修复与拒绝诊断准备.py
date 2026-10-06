"""在首轮真实候选上新增零位移边收缩及可关闭生成轨迹，保留首轮冻结代码。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json

here=Path(__file__).resolve().parent
output=here/'第二轮零位移收缩与生成诊断'
output.mkdir()
source=here/'候选内核源码'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
before=json.loads((here/'10-隔离内核候选源码准备清单.json').read_text('utf8'))
for name,digest in before['files'].items(): assert sha(source/name)==digest
main=(source/'mesh_surface_intersection.cpp').read_text('utf8')
needle='    void copy_operand(Mesh& result, const Mesh& operand, index_t operand_id) {'
assert main.count(needle)==1
main=main.replace(needle,(here/'34-双精度零长度边合法收缩.cpp').read_text('utf8')+'\n\n'+needle)
main=main.replace('#include <geogram/delaunay/CDT_2d.h>','#include <geogram/delaunay/CDT_2d.h>\n#include <set>\n#include <iterator>')
needle='        I.classify(operation);'
assert main.count(needle)==1
main=main.replace(needle,needle+'''\n        // 分类完成后处理双精度表示中的零长度边，不重写原版准确交点表。
        contract_collapsed_float_edges(result);''')
internal=(source/'mesh_surface_intersection_internal.cpp').read_text('utf8')
needle='    valid=valid && returned_boundaries==boundaries;'
assert internal.count(needle)==1
internal=internal.replace(needle,needle+'\n    bool boundary_unchanged=valid;')
needle='    release();\n    return valid;'
assert internal.count(needle)==1
internal=internal.replace(needle,'''    // 开发诊断可开启逐区域轨迹，正式计时不启用该环境变量。
    if(std::getenv("GEO_NATIVE_QUALITY_TRACE")!=nullptr) {
        std::lock_guard<std::mutex> guard(triangle_mutex);
        std::cerr << "NATIVE_QUALITY_REGION {\\\"group\\\":" << group_id_
                  << ",\\\"source_facets\\\":" << facets_.size()
                  << ",\\\"boundary_points\\\":" << ids.size()
                  << ",\\\"new_points\\\":" << output.numberofpoints-int(ids.size())
                  << ",\\\"boundary_unchanged\\\":" << (boundary_unchanged ? "true" : "false")
                  << ",\\\"before_bad\\\":" << before.bad
                  << ",\\\"after_bad\\\":" << after.bad
                  << ",\\\"after_valid\\\":" << (after.valid ? "true" : "false")
                  << ",\\\"before_bad_area\\\":" << double(before.area)
                  << ",\\\"after_bad_area\\\":" << double(after.area)
                  << ",\\\"selected\\\":" << (valid ? "true" : "false") << "}" << std::endl;
    }
    release();
    return valid;''')
for name,text in [('mesh_surface_intersection.cpp',main),('mesh_surface_intersection_internal.cpp',internal),
                  ('mesh_surface_intersection_internal.h',(source/'mesh_surface_intersection_internal.h').read_text('utf8'))]:
    (output/name).write_text(text,'utf8')
receipt={'生成时间':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),
         '修改时间及修改内容':'首次第二轮零长度边链接收缩及拒绝轨迹源码准备',
         '文档概述':'坐标逐值不变；仅合法零长度边；内核细化原参数不改',
         '索引目录':['files'],'status':'prepared_second_native_zero_edge_and_trace_sources',
         'prior_source_manifest_sha256':sha(here/'10-隔离内核候选源码准备清单.json'),
         'files':{p.name:sha(p) for p in output.iterdir()},'trace_enabled_in_benchmark':False}
(here/'36-第二轮零位移收缩与生成诊断源码清单.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n','utf8')
print('第二轮原生源码已准备',flush=True)
