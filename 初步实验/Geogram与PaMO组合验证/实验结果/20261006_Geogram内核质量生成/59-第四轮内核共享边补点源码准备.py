"""依据窄缝拒绝轨迹，加入准确共享边补点与整体质量回退。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json

here=Path(__file__).resolve().parent
source=here/'第三轮收缩顺序与精确索引修订'
output=here/'第四轮准确共享边补点生成'
# 首次断言失败只留下空目录，恢复仅允许空目录，不覆盖任何已生成源码。
if output.exists(): assert not any(output.iterdir())
else: output.mkdir()
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
prior=json.loads((here/'44-第三轮内部顺序与索引修订源码清单.json').read_text('utf8'))
for name,digest in prior['files'].items(): assert sha(source/name)==digest
internal=(source/'mesh_surface_intersection_internal.cpp').read_text('utf8')
old='vector<index_t>& triangles, vector<ExactPoint>& new_points'
assert internal.count(old)==1
internal=internal.replace(old,old+', vector<std::pair<index_t,index_t>>& boundary_edges')
internal=internal.replace('// 此方法在Geogram区域三角化阶段执行，保持已有边界，直接生成返回网格。',
                          '// 此方法在Geogram区域三角化阶段提出准确共边补点，最终由内核统一保持相邻面一致。')
internal=internal.replace('    triangulateio input{},output{};',
'''    // 每条约束段使用独立标记，返回子段据此归回同一准确原边。
    vector<int> markers(segments.size()/2);
    for(index_t i=0;i<markers.size();++i) markers[i]=int(i)+1;
    triangulateio input{},output{};''')
internal=internal.replace('input.segmentlist=segments.data(); input.numberofsegments=int(segments.size()/2);',
                         'input.segmentlist=segments.data(); input.numberofsegments=int(segments.size()/2); input.segmentmarkerlist=markers.data();')
internal=internal.replace('// 保留已有约束段并禁止边界补点，新增内部点最多六十四个。',
                         '// 允许约束段内补点，内部和边界新增点合计最多六十四个；共享边由统一提交同步。')
internal=internal.replace('rpzq20YYS64Q','rpzq20S64Q')
start=internal.index('    std::set<std::pair<int,int>> returned_boundaries;',internal.index('bool CoplanarFacets::quality_triangulate'))
end=internal.index('    // 新内部点准确提升到原支撑平面',start)
internal=internal[:start]+'''    vector<int> on_segment(output.numberofpoints,-1);
    vector<vector<std::pair<int,int>>> chains(markers.size());
    valid=valid && output.segmentmarkerlist!=nullptr;
    for(int i=0;valid && i<output.numberofsegments;++i) {
        int a=output.segmentlist[2*i],b=output.segmentlist[2*i+1],m=output.segmentmarkerlist[i]-1;
        valid=a>=0 && b>=0 && a<output.numberofpoints && b<output.numberofpoints && m>=0 && m<int(chains.size());
        if(!valid) break;
        chains[m].push_back({a,b});
        for(int v:{a,b}) if(v>=int(ids.size())) {
            if(on_segment[v]!=-1 && on_segment[v]!=m) valid=false;
            on_segment[v]=m;
        }
    }
    // 每条原约束必须返回无分叉的完整端点链，不接受额外孔洞边或缺失约束。
    for(index_t m=0;valid && m<chains.size();++m) {
        std::map<int,std::set<int>> neighbors;
        for(auto edge:chains[m]) {neighbors[edge.first].insert(edge.second);neighbors[edge.second].insert(edge.first);}
        int a=segments[2*m],b=segments[2*m+1];
        valid=neighbors[a].size()==1 && neighbors[b].size()==1 && chains[m].size()+1==neighbors.size();
        std::set<int> visited;vector<int> stack={a};
        while(!stack.empty()) {
            int v=stack.back();stack.pop_back();
            if(!visited.insert(v).second) continue;
            valid=valid && neighbors[v].size()==(v==a || v==b ? 1u : 2u);
            for(int q:neighbors[v]) stack.push_back(q);
        }
        valid=valid && visited.size()==neighbors.size();
    }
    bool boundary_unchanged=valid;
    vector<std::pair<index_t,index_t>> proposed_boundaries;

'''+internal[end:]
internal=internal.replace('// 新内部点准确提升到原支撑平面，原边界顶点及坐标逐项保持。',
                         '// 内部点准确提升到支撑平面；边界点用原准确端点插值，端点坐标逐项保持。')
start=internal.index('        p.w=normal[k]*a.w;',internal.index('bool CoplanarFacets::quality_triangulate'))
end=internal.index('        Numeric::optimize_number_representation(p);',start)
internal=internal[:start]+'''        int segment=on_segment[i];
        if(segment>=0) {
            int ia=segments[2*segment],ib=segments[2*segment+1];
            int axis=std::abs(xy[2*ib]-xy[2*ia])>=std::abs(xy[2*ib+1]-xy[2*ia+1]) ? 0 : 1;
            double divisor=xy[2*ib+axis]-xy[2*ia+axis];
            double t=(output.pointlist[2*i+axis]-xy[2*ia+axis])/divisor;
            valid=std::isfinite(t) && t>0.0 && t<1.0;
            if(!valid) break;
            ExactPoint pa=I_.exact_vertex(ids[ia]),pb=I_.exact_vertex(ids[ib]);
            p.w=pa.w*pb.w;
            for(coord_index_t d=0;d<3;++d) p[d]=pa[d]*pb.w+(pb[d]*pa.w-pa[d]*pb.w)*t;
            proposed_boundaries.push_back(std::minmax(ids[ia],ids[ib]));
        } else {
            p.w=normal[k]*a.w;
            p[u_]=x*p.w; p[v_]=y*p.w;
            p[k]=normal.x*a.x+normal.y*a.y+normal.z*a.z-a.w*(normal[u_]*x+normal[v_]*y);
            proposed_boundaries.push_back({NO_INDEX,NO_INDEX});
        }
'''+internal[end:]
internal=internal.replace('        new_points.swap(proposed);','        new_points.swap(proposed);\n        boundary_edges.swap(proposed_boundaries);')
header=(source/'mesh_surface_intersection_internal.h').read_text('utf8')
header=header.replace('// 在原区域内生成质量候选，边界不变；返回的新点尚未写入共享网格。',
                      '// 区域提出内部和准确共边新点；共边端点编号随新点返回，供内核同步相邻面。')
header=header.replace('vector<index_t>& triangles, vector<ExactPoint>& new_points);',
                      'vector<index_t>& triangles, vector<ExactPoint>& new_points, vector<std::pair<index_t,index_t>>& boundary_edges);')
main=(source/'mesh_surface_intersection.cpp').read_text('utf8')
needle='namespace {\n    using namespace GEO;'
assert main.count(needle)>=1
main=main.replace(needle,needle+'\n'+(here/'58-共享边补点一致提交与整体质量检查.cpp').read_text('utf8'),1)
main=main.replace('''            vector<ExactPoint> new_points;
        };''','''            vector<ExactPoint> new_points;
            vector<std::pair<index_t,index_t>> boundary_edges;
            vector<index_t> reference_triangles;
        };''')
main=main.replace('        const index_t original_vertices=mesh_.vertices.nb();',
                  '        const index_t original_vertices=mesh_.vertices.nb();\n        const index_t original_facets=mesh_.facets.nb();')
needle='''                    QualityRegion& region=regions[group];
                    if(!coplanar.quality_triangulate(region.triangles,region.new_points)) {'''
assert main.count(needle)==1
main=main.replace(needle,'''                    QualityRegion& region=regions[group];
                    // 保存原版CDT同区域结果，整体检查失败时回到这份准确生成结果。
                    for(index_t t=0;t<coplanar.CDT.nT();++t) for(index_t k=0;k<3;++k) {
                        region.reference_triangles.push_back(coplanar.CDT.vertex_id(coplanar.CDT.Tv(t,k)));
                    }
                    if(!coplanar.quality_triangulate(region.triangles,region.new_points,region.boundary_edges)) {''')
main=main.replace('''        for(QualityRegion& region:regions) {
            vector<index_t> ids;''','''        std::map<std::pair<index_t,index_t>,vector<index_t>> shared_splits;
        vector<index_t> reference;
        for(index_t f=0;f<original_facets;++f) if(!remove_f[f]) {
            for(index_t k=0;k<3;++k) reference.push_back(mesh_.facets.vertex(f,k));
        }
        for(QualityRegion& region:regions) {
            reference.insert(reference.end(),region.reference_triangles.begin(),region.reference_triangles.end());
            vector<index_t> ids;''')
needle='''            for(index_t i=0; i<region.triangles.size(); i+=3) {'''
assert main.count(needle)==1
main=main.replace(needle,'''            for(index_t i=0;i<region.boundary_edges.size();++i) {
                if(region.boundary_edges[i].first!=NO_INDEX) shared_splits[region.boundary_edges[i]].push_back(ids[i]);
            }
'''+needle)
needle='''\t// Delete temporary attributes
\tfacet_group.destroy();'''
assert main.count(needle)==1
main=main.replace(needle,'''        // 生成提交仍在Geogram内部：先同步共边链，再检查整个候选的绝对质量。
        conform_quality_boundary_splits(mesh_,remove_f,shared_splits);
        remove_f.resize(mesh_.facets.nb(),0);
        vector<index_t> proposed_cells;
        for(index_t f:mesh_.facets) if(!remove_f[f]) for(index_t k=0;k<3;++k) proposed_cells.push_back(mesh_.facets.vertex(f,k));
        NativeQualityScore baseline_score=native_quality_score(mesh_,reference);
        NativeQualityScore candidate_score=native_quality_score(mesh_,proposed_cells);
        // 浮点求和容差仅按机器精度和本次总面积计算，不设置物理误差门槛。
        long double summation_tolerance=128.0L*std::numeric_limits<double>::epsilon()*baseline_score.total_area;
        bool accept=candidate_score.finite && candidate_score.zero<=baseline_score.zero &&
            candidate_score.bad<=baseline_score.bad && candidate_score.area<=baseline_score.area+summation_tolerance;
        if(!accept) {
            for(index_t f=original_facets;f<mesh_.facets.nb();++f) remove_f[f]=1;
            for(index_t i=0;i<reference.size();i+=3) {
                mesh_.facets.create_triangle(reference[i],reference[i+1],reference[i+2]);remove_f.push_back(0);
            }
            // 未替换的原面已包含在参照列表中，回退时统一改用这份完整列表。
            for(index_t f=0;f<original_facets;++f) remove_f[f]=1;
        }
        Logger::out("QualityBoundary") << "shared_edges=" << shared_splits.size()
            << " before_bad=" << baseline_score.bad << " after_bad=" << candidate_score.bad
            << " before_area=" << double(baseline_score.area) << " after_area=" << double(candidate_score.area)
            << " accepted=" << accept << std::endl;

'''+needle)
main=main.replace('#include <cmath>','#include <cmath>\n#include <limits>')
for name,text in [('mesh_surface_intersection.cpp',main),('mesh_surface_intersection_internal.cpp',internal),
                  ('mesh_surface_intersection_internal.h',header)]: (output/name).write_text(text,'utf8')
record={'生成时间':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),
        '修改时间及修改内容':'准确边界插值、共享边一致同步及全网格数量面积回退',
        '文档概述':'第四轮原生生成开发候选；原有版本冻结保留',
        '索引目录':['files'],'status':'prepared_fourth_native_shared_boundary_generation',
        'prior_manifest_sha256':sha(here/'44-第三轮内部顺序与索引修订源码清单.json'),
        'files':{p.name:sha(p) for p in output.iterdir()},'quality_options':'rpzq20S64Q'}
(here/'60-第四轮准确共享边生成源码清单.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n','utf8')
builder=(here/'45-第三轮原生内核独立编译.py').read_text('utf8').replace('第三轮','第四轮')
(here/'61-第四轮原生内核独立编译.py').write_text(builder,'utf8')
controller=(here/'46-第三轮隔离编译上传与执行.py').read_text('utf8')
for old,new in [('第三轮','第四轮'),('20261006_04','20261006_05'),
                ('44-第四轮内部顺序与索引修订源码清单.json','60-第四轮准确共享边生成源码清单.json'),
                ('第四轮收缩顺序与精确索引修订','第四轮准确共享边补点生成'),
                ('45-第四轮原生内核独立编译.py','61-第四轮原生内核独立编译.py'),
                ('47-第四轮实际编译执行记录.json','63-第四轮实际编译执行记录.json'),
                ('48-第四轮实际编译控制台日志.txt','64-第四轮实际编译控制台日志.txt'),
                ('49-第四轮实际原生编译记录.json','65-第四轮实际原生编译记录.json')]: controller=controller.replace(old,new)
(here/'62-第四轮隔离编译上传与执行.py').write_text(controller,'utf8')
print('第四轮内部准确共享边生成源码已准备')
