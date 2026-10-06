"""依据实际重放证据，保留内部点优先，并在共边补点后原生重生成相邻区域。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json

here=Path(__file__).resolve().parent
source=here/'第五轮共享子边同步生成'
output=here/'第七轮内部点优先与共边邻域重生成';output.mkdir()
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
prior=json.loads((here/'68-第五轮共享子边同步源码清单.json').read_text('utf8'))
for name,digest in prior['files'].items(): assert sha(source/name)==digest
internal=(source/'mesh_surface_intersection_internal.cpp').read_text('utf8')
old='vector<index_t>& triangles, vector<ExactPoint>& new_points, vector<std::pair<index_t,index_t>>& boundary_edges'
assert internal.count(old)==1
internal=internal.replace(old,old+', bool allow_boundary, index_t point_budget, bool boundary_attempt')
internal=internal.replace('#include <cmath>','#include <cmath>\n#include <limits>\n#include <cstdio>')
old='''    // 双精度投影已失去正面积的区域保留准确CDT，不送入浮点细化器。
    for(index_t i=0; i<cells.size(); i+=3) {'''
new='''    // 先检查相对于区域尺度的机器精度余量，极短边保留准确CDT，避免浮点补点重合。
    double low[2]={xy[0],xy[1]},high[2]={xy[0],xy[1]},shortest=Numeric::max_float64();
    for(index_t i=0;i<ids.size();++i) for(index_t d=0;d<2;++d) {
        low[d]=std::min(low[d],xy[2*i+d]);high[d]=std::max(high[d],xy[2*i+d]);
    }
    double extent=std::max(high[0]-low[0],high[1]-low[1]);
    for(index_t i=0;i<cells.size();i+=3) for(index_t k=0;k<3;++k) {
        int a=cells[i+k],b=cells[i+(k+1)%3];
        double x=xy[2*a]-xy[2*b],y=xy[2*a+1]-xy[2*b+1];
        shortest=std::min(shortest,std::hypot(x,y));
    }
    double floating_margin=128.0*std::numeric_limits<double>::epsilon()*extent;
    if(shortest<=floating_margin) return false;
    // 双精度投影已失去正面积的区域保留准确CDT，不送入浮点细化器。
    for(index_t i=0; i<cells.size(); i+=3) {'''
assert internal.count(old)==1;internal=internal.replace(old,new)
old='''    // 允许约束段内补点，内部和边界新增点合计最多六十四个；共享边由统一提交同步。
    char options[]="rpzq20S64Q";'''
new='''    // 默认只补内部点；仅面积拒绝的改善候选才尝试共边补点，并保留确定上限。
    char options[64];
    std::snprintf(options,sizeof(options),"rpzq20%sS%uQ",boundary_attempt ? "" : "YY",unsigned(point_budget));'''
assert internal.count(old)==1;internal=internal.replace(old,new)
internal=internal.replace('output.numberofpoints<=int(ids.size())+64','output.numberofpoints<=int(ids.size())+int(point_budget)')
internal=internal.replace('<< ",\\"source_facets\\":" << facets_.size()',
                          '<< ",\\"boundary_attempt\\":" << (boundary_attempt ? "true" : "false")\n                  << ",\\"point_budget\\":" << point_budget\n                  << ",\\"source_facets\\":" << facets_.size()')
old='''    release();
    return valid;
#endif'''
new='''    release();
    // 点数改善但坏面面积上升时，再试一次有界边界细化，不能放松原质量判定。
    if(!valid && allow_boundary && !boundary_attempt && after_score_computed &&
       after.bad<before.bad && after.area>before.area) {
        return quality_triangulate(triangles,new_points,boundary_edges,true,128,true);
    }
    return valid;
#endif'''
assert internal.count(old)==1;internal=internal.replace(old,new)
header=(source/'mesh_surface_intersection_internal.h').read_text('utf8')
header=header.replace('vector<std::pair<index_t,index_t>>& boundary_edges);',
                      'vector<std::pair<index_t,index_t>>& boundary_edges, bool allow_boundary, index_t point_budget, bool boundary_attempt = false);')
main=(source/'mesh_surface_intersection.cpp').read_text('utf8')
needle='namespace {\n    using namespace GEO;'
main=main.replace(needle,needle+'\n    // 只允许一次共边补点后的邻域再生成，防止递归质量细化失去固定预算。\n    thread_local index_t quality_neighbor_depth = 0;',1)
main=main.replace('        vector<index_t> remove_f(mesh_.facets.nb(), 0);\n        index_t nb_groups',
'''        // 共边新点在相邻区域再生成时必须保留，禁止共线简化把接缝补点删除。
        Attribute<bool> quality_anchor(mesh_.vertices.attributes(),"quality_boundary_anchor");
        for(index_t v:mesh_.vertices) if(quality_anchor[v]) keep_vertex[v]=true;
        const bool allow_boundary_generation=(quality_neighbor_depth==0);
        vector<index_t> remove_f(mesh_.facets.nb(), 0);
        index_t nb_groups''')
main=main.replace('coplanar.quality_triangulate(region.triangles,region.new_points,region.boundary_edges)',
                  'coplanar.quality_triangulate(region.triangles,region.new_points,region.boundary_edges,allow_boundary_generation,allow_boundary_generation ? 64 : 128)')
main=main.replace('''        for(QualityRegion& region:regions) {
            reference.insert''','''        index_t committed_group=0;
        for(QualityRegion& region:regions) {
            reference.insert''')
old='''                if(region.boundary_edges[i].first!=NO_INDEX) shared_splits[region.boundary_edges[i]].push_back(ids[i]);'''
new='''                if(region.boundary_edges[i].first!=NO_INDEX) {
                    shared_splits[region.boundary_edges[i]].push_back(ids[i]);quality_anchor[ids[i]]=true;
                }'''
assert main.count(old)==1;main=main.replace(old,new)
old='''                facet_group[new_f]=current_group;
            }
        }

        // 生成提交仍在Geogram内部'''
new='''                // 邻域再生成仍需原输入面来源，不能把新面默认归到零号输入面。
                mesh_.facets.attributes().copy_item(new_f,group_facet[committed_group]);
                facet_group[new_f]=committed_group;
            }
            ++committed_group;
        }

        // 生成提交仍在Geogram内部'''
assert main.count(old)==1;main=main.replace(old,new)
old='''        conform_quality_boundary_splits(mesh_,remove_f,shared_splits);
        remove_f.resize(mesh_.facets.nb(),0);
        vector<index_t> proposed_cells;'''
new='''        conform_quality_boundary_splits(mesh_,remove_f,shared_splits);
        remove_f.resize(mesh_.facets.nb(),0);
        bool rebuilt_shared_neighbors=false;
        if(!shared_splits.empty() && allow_boundary_generation) {
            // 准确点编号和整体参照仍要继续使用，此处只压缩面，不压缩顶点。
            mesh_.facets.delete_elements(remove_f,false);mesh_.facets.connect();
            facet_group.unbind();keep_vertex.unbind();
            ++quality_neighbor_depth;
            simplify_coplanar_facets(angle_tolerance);
            --quality_neighbor_depth;
            remove_f.assign(mesh_.facets.nb(),0);rebuilt_shared_neighbors=true;
        }
        vector<index_t> proposed_cells;'''
assert main.count(old)==1;main=main.replace(old,new)
old='''        if(!accept) {
            for(index_t f=original_facets;f<mesh_.facets.nb();++f) remove_f[f]=1;'''
new='''        if(!accept) {
            // 所有参照编号仍有效；整体失败时删除全部暂定面并恢复完整原版CDT列表。
            for(index_t f=0;f<mesh_.facets.nb();++f) remove_f[f]=1;'''
assert main.count(old)==1;main=main.replace(old,new)
old='''            // 未替换的原面已包含在参照列表中，回退时统一改用这份完整列表。
            for(index_t f=0;f<original_facets;++f) remove_f[f]=1;
'''
assert main.count(old)==1;main=main.replace(old,'')
old='''\t// Delete temporary attributes
\tfacet_group.destroy();
\tkeep_vertex.destroy();

        remove_f.resize(mesh_.facets.nb(),0);
        mesh_.facets.delete_elements(remove_f);
        mesh_.facets.connect();'''
new='''        // 邻域递归已经清理同名临时属性，外层已解绑，避免重复销毁。
        if(!rebuilt_shared_neighbors) {facet_group.destroy();keep_vertex.destroy();}
        if(quality_neighbor_depth==0) quality_anchor.destroy();
        remove_f.resize(mesh_.facets.nb(),0);
        // 外层整体核查结束后才压缩顶点，递归内部保持准确点与参照编号稳定。
        mesh_.facets.delete_elements(remove_f,quality_neighbor_depth==0);
        mesh_.facets.connect();'''
assert main.count(old)==1;main=main.replace(old,new)
for name,text in [('mesh_surface_intersection.cpp',main),('mesh_surface_intersection_internal.cpp',internal),
                  ('mesh_surface_intersection_internal.h',header)]: (output/name).write_text(text,'utf8')
record={'生成时间':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),
        '修改时间及修改内容':'内部点优先、有界共边回退、固定接缝锚点及一次邻域再生成',
        '文档概述':'依据真实捕获与重放修订；先编译和完整评价，不提前称达标',
        '索引目录':['files'],'status':'prepared_seventh_native_bounded_neighbor_regeneration',
        'files':{p.name:sha(p) for p in output.iterdir()},'prior_manifest_sha256':sha(here/'68-第五轮共享子边同步源码清单.json'),
        'internal_point_budget':64,'boundary_attempt_budget':128,'neighbor_internal_budget':128,'neighbor_passes_max':1,
        'relative_float_margin':'128 times double epsilon times projected region extent'}
(here/'110-有界共边与邻域再生成源码清单.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n','utf8')
builder=(here/'69-第五轮原生内核独立编译.py').read_text('utf8').replace('第五轮','第七轮')
(here/'111-有界邻域生成原生独立编译.py').write_text(builder,'utf8')
controller=(here/'70-第五轮隔离编译上传与执行.py').read_text('utf8')
for old,new in [('第五轮','第七轮'),('20261006_06','20261006_08'),
                ('68-第七轮共享子边同步源码清单.json','110-有界共边与邻域再生成源码清单.json'),
                ('第七轮共享子边同步生成','第七轮内部点优先与共边邻域重生成'),
                ('69-第七轮原生内核独立编译.py','111-有界邻域生成原生独立编译.py'),
                ('71-第七轮实际编译执行记录.json','113-有界邻域生成实际编译执行记录.json'),
                ('72-第七轮实际编译控制台日志.txt','114-有界邻域生成实际编译控制台日志.txt'),
                ('73-第七轮实际原生编译记录.json','115-有界邻域生成实际原生编译记录.json')]:controller=controller.replace(old,new)
(here/'112-有界邻域生成隔离编译上传执行.py').write_text(controller,'utf8')
print('有界共边及邻域再生成原生源码已准备')
