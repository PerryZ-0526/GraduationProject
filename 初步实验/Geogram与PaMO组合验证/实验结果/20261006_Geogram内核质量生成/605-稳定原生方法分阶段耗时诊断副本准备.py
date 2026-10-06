"""仅增加独立分阶段计时，正式封存方法和参数保持不变。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json
import shutil

here=Path(__file__).resolve().parent
folder=here/'稳定原生方法分阶段计时诊断源码';folder.mkdir()
frozen=json.loads((here/'569-新边拒绝原生主候选完整开发终态封存清单.json').read_text('utf8'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
for name in ['mesh_surface_intersection.cpp','mesh_surface_intersection_internal.cpp','mesh_surface_intersection_internal.h']:
    p=here/'新边拒绝固定原生候选封存'/name;assert sha(p)==frozen['files'][name];shutil.copy2(p,folder/name)
path=folder/'mesh_surface_intersection.cpp';source=path.read_text('utf8')
source=source.replace('#include <set>','#include <set>\n// 独立诊断副本的单调时钟只测执行耗时，记录时间由控制器按北京时间保存。\n#include <chrono>')
begin=source.index('    void mesh_boolean_operation(')
end=source.index('    void mesh_remove_intersections(',begin)
body=source[begin:end]
anchor='\tbool verbose = ((flags & MESH_BOOL_OPS_VERBOSE) != 0);'
assert body.count(anchor)==1
body=body.replace(anchor,anchor+'''
        // 仅环境变量开启诊断，算法输入、判断与返回对象保持原规则。
        const bool trace_stage=std::getenv("GEO_NATIVE_STAGE_TIMING")!=nullptr;
        auto trace_start=std::chrono::steady_clock::now();
        auto trace_step=[&](const char* name) {
            if(trace_stage) {
                auto finish=std::chrono::steady_clock::now();
                double ms=std::chrono::duration<double,std::milli>(finish-trace_start).count();
                std::fprintf(stderr,"NATIVE_PROFILE_STAGE %s %.9f\\n",name,ms);
                trace_start=std::chrono::steady_clock::now();
            }
        };''')
body=body.replace('''        // 在产生交点之前冻结真实输入坐标''','''        trace_step("copy_operands");
        // 在产生交点之前冻结真实输入坐标''')
body=body.replace('''        MeshSurfaceIntersection I(result);''','''        trace_step("freeze_input_coordinates");
        MeshSurfaceIntersection I(result);''')
body=body.replace('''        I.intersect();
        I.classify(operation);''','''        I.intersect();trace_step("intersect");
        I.classify(operation);trace_step("classify");''')
body=body.replace('''\t    I.simplify_coplanar_facets();''','''            trace_step("pre_coplanar_cleanup");
\t    I.simplify_coplanar_facets();trace_step("coplanar_quality");''')
body=body.replace('''        while(contract_collapsed_float_edges(result,quality_original_coordinates)!=0) {
        }
    }''','''        while(contract_collapsed_float_edges(result,quality_original_coordinates)!=0) {
        }
        trace_step("post_coplanar_cleanup");
    }''')
source=source[:begin]+body+source[end:]
begin=source.index('    void MeshSurfaceIntersection::simplify_coplanar_facets(')
end=source.index('index_t contract_collapsed_float_edges(',begin)
body=source[begin:end]
anchor='''        Attribute<index_t> facet_group(mesh_.facets.attributes(), "group");'''
assert body.count(anchor)==1
body=body.replace(anchor,'''        // 共面子阶段分别计时；递归深度区分后只按对应父阶段解释，不重复相加。
        const bool trace_coplanar=std::getenv("GEO_NATIVE_STAGE_TIMING")!=nullptr;
        auto trace_coplanar_start=std::chrono::steady_clock::now();
        auto trace_coplanar_step=[&](const char* name) {
            if(trace_coplanar) {
                auto finish=std::chrono::steady_clock::now();
                double ms=std::chrono::duration<double,std::milli>(finish-trace_coplanar_start).count();
                std::fprintf(stderr,"NATIVE_PROFILE_COPLANAR depth=%u %s %.9f\\n",unsigned(quality_neighbor_depth),name,ms);
                trace_coplanar_start=std::chrono::steady_clock::now();
            }
        };
'''+anchor)
body=body.replace('''        // 并行阶段只读取共享网格''','''        trace_coplanar_step("discover_groups_and_anchors");
        // 并行阶段只读取共享网格''')
body=body.replace('''        // 全部区域读取结束后统一提交''','''        trace_coplanar_step("parallel_region_cdt_and_proposals");
        // 全部区域读取结束后统一提交''')
body=body.replace('''        // 生成提交仍在Geogram内部''','''        trace_coplanar_step("commit_exact_vertices_and_facets");
        // 生成提交仍在Geogram内部''')
body=body.replace('''        conform_quality_boundary_splits(mesh_,remove_f,shared_splits);
        remove_f.resize''','''        conform_quality_boundary_splits(mesh_,remove_f,shared_splits);
        trace_coplanar_step("conform_shared_boundary");
        remove_f.resize''')
body=body.replace('''        bool rebuilt_shared_neighbors=false;''','''        trace_coplanar_step("whole_candidate_scores");
        bool rebuilt_shared_neighbors=false;''')
body=body.replace('''        // 只有确实执行邻域再生成''','''        trace_coplanar_step("recursive_shared_neighbors_or_rejection");
        // 只有确实执行邻域再生成''')
body=body.replace('''        mesh_.facets.connect();
    }''','''        mesh_.facets.connect();trace_coplanar_step("restore_and_compact");
    }''')
source=source[:begin]+body+source[end:];path.write_text(source,'utf8')
path=folder/'mesh_surface_intersection_internal.cpp';source=path.read_text('utf8')
source=source.replace('#include <mutex>','#include <mutex>\n// Triangle计时仅在诊断变量开启时打印，不作为正式速度样本。\n#include <chrono>')
anchor='''        ::triangulate(options,&input,&output,nullptr);'''
assert source.count(anchor)==1
source=source.replace(anchor,'''        auto triangle_start=std::chrono::steady_clock::now();
        ::triangulate(options,&input,&output,nullptr);
        // 串行调用实际计算耗时；不把互斥等待时间并入本项。
        if(std::getenv("GEO_NATIVE_STAGE_TIMING")) {
            double ms=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-triangle_start).count();
            std::fprintf(stderr,"NATIVE_PROFILE_TRIANGLE group=%u boundary=%u budget=%u ms=%.9f\\n",unsigned(group_id_),unsigned(boundary_attempt),unsigned(point_budget),ms);
        }''')
path.write_text(source,'utf8')
record={'生成时间':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),
 '修改时间及修改内容':'首次稳定方法独立阶段耗时诊断副本',
 '文档概述':'算法不改，仅阶段时间诊断；正式计时仍使用569号实际方法',
 '索引目录':['files'],'prior_method_sha256':sha(here/'569-新边拒绝原生主候选完整开发终态封存清单.json'),
 'files':{p.name:sha(p) for p in folder.iterdir() if p.is_file()}}
(here/'606-稳定原生阶段计时诊断源码清单.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n','utf8')
(here/'607-稳定原生阶段计时诊断独立编译.py').write_text((here/'591-保留好区顶点免重建原生独立编译.py').read_text('utf8'),'utf8')
controller=(here/'592-保留好区顶点免重建上传编译.py').read_text('utf8')
for old,new in [('20261007_30','20261007_31'),('590-保留好区顶点免重建源码清单','606-稳定原生阶段计时诊断源码清单'),('第二十三轮保留好区顶点免重建','稳定原生方法分阶段计时诊断源码'),('591-保留好区顶点免重建原生独立编译','607-稳定原生阶段计时诊断独立编译'),('593-保留好区顶点免重建实际编译执行记录','609-稳定原生阶段计时诊断实际编译执行记录'),('594-保留好区顶点免重建实际编译控制台日志','610-稳定原生阶段计时诊断实际编译控制台日志'),('595-保留好区顶点免重建实际原生编译记录','611-稳定原生阶段计时诊断实际原生编译记录'),('保留好区顶点免重建_','稳定原生阶段计时诊断_')]:controller=controller.replace(old,new)
(here/'608-稳定原生阶段计时诊断上传编译.py').write_text(controller,'utf8')
print('prepared_stage_profile_only')
