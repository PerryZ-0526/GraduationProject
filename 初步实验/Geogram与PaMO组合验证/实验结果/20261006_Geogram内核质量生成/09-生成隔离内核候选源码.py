"""仅修改原版三份生成阶段源码，保留作者原文件和所有未改注释。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json

here=Path(__file__).resolve().parent
folder=here/'候选内核源码'
folder.mkdir()
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
internal=(here/'02-原版远端区域三角化源码.cpp').read_text('utf8')
header=(here/'06-原版远端区域三角化头文件.h').read_text('utf8')
main=(here/'07-原版远端布尔生成源码.cpp').read_text('utf8')
needle='    bool CoplanarFacets::triangles_are_coplanar('
assert internal.count(needle)==1
helper=(here/'08-内核有界内部点质量三角化.cpp').read_text('utf8')
internal=internal.replace(needle,helper+'\n\n'+needle)
needle='#include <geogram/mesh/mesh_surface_intersection_internal.h>'
assert internal.count(needle)==1
internal=internal.replace(needle,needle+'\n#include <geogram/delaunay/delaunay_triangle.h>\n#include <mutex>\n#include <set>\n#include <cmath>')
position=header.index('class CoplanarFacets')
needle='        void triangulate();'
offset=header.index(needle,position)+len(needle)
header=header[:offset]+'''\n\n        // 在原区域内生成质量候选，边界不变；返回的新点尚未写入共享网格。
        bool quality_triangulate(vector<index_t>& triangles, vector<ExactPoint>& new_points);
'''+header[offset:]
start=main.index('        // Avoid to have reallocations in parallel with access by',main.index('void MeshSurfaceIntersection::simplify_coplanar_facets('))
end=main.index('\t// Delete temporary attributes',start)
main=main[:start]+'''        // 并行阶段只读取共享网格，区域内部点及面暂存在各自的结果中。
        struct QualityRegion {
            vector<index_t> triangles;
            vector<ExactPoint> new_points;
        };
        vector<QualityRegion> regions(nb_groups);
        const index_t original_vertices=mesh_.vertices.nb();
        parallel_for_slice(
            0, nb_groups, [&](index_t b, index_t e) {
                // 不清空已建立的区域属性，各线程独立构造区域三角化对象。
                CoplanarFacets coplanar(*this,false,angle_tolerance);
                for(index_t group=b; group<e; ++group) {
                    coplanar.get(group_facet[group],group);
                    if(coplanar.nb_facets()<2) continue;
                    coplanar.triangulate();
                    bool OK=true;
                    // 保持原版外包四边形顶点检查，任何未分类外部面都不提交。
                    for(index_t t=0; t<coplanar.CDT.nT(); ++t) {
                        for(index_t k=0; k<3; ++k) {
                            OK=OK && coplanar.CDT.vertex_id(coplanar.CDT.Tv(t,k))!=NO_INDEX;
                        }
                    }
                    if(!OK) continue;
                    coplanar.mark_facets(remove_f);
                    QualityRegion& region=regions[group];
                    if(!coplanar.quality_triangulate(region.triangles,region.new_points)) {
                        for(index_t t=0; t<coplanar.CDT.nT(); ++t) {
                            for(index_t k=0; k<3; ++k) {
                                region.triangles.push_back(coplanar.CDT.vertex_id(coplanar.CDT.Tv(t,k)));
                            }
                        }
                    }
                }
            }
        );
        // 全部区域读取结束后统一提交准确内部点，避免扩容破坏并行读者。
        for(QualityRegion& region:regions) {
            vector<index_t> ids;
            for(const ExactPoint& point:region.new_points) {
                ids.push_back(find_or_create_exact_vertex(point));
            }
            for(index_t i=0; i<region.triangles.size(); i+=3) {
                index_t vertices[3];
                for(index_t k=0; k<3; ++k) {
                    index_t v=region.triangles[i+k];
                    vertices[k]=v<original_vertices ? v : ids[v-original_vertices];
                }
                index_t new_f=mesh_.facets.create_triangle(vertices[0],vertices[1],vertices[2]);
                facet_group[new_f]=current_group;
            }
        }

'''+main[end:]
for name,content in [('mesh_surface_intersection_internal.cpp',internal),
                     ('mesh_surface_intersection_internal.h',header),('mesh_surface_intersection.cpp',main)]:
    (folder/name).write_text(content,'utf8')
stamp=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
receipt={'生成时间':stamp,'修改时间及修改内容':'首次准备内部质量三角化原生候选','文档概述':'Geogram内部区域生成；原边界不变；不接Python维护','索引目录':['files','mechanism'],
         'status':'prepared_candidate_kernel_source','files':{p.name:sha(p) for p in folder.iterdir()},
         'originals':{name:sha(here/name) for name in ['02-原版远端区域三角化源码.cpp','06-原版远端区域三角化头文件.h','07-原版远端布尔生成源码.cpp']},
         'mechanism':{'triangle_switches':'rpzq20YYS64Q','internal_point_limit_per_region':64,
                      'boundary_points_unchanged':True,'require_bad_count_and_area_nonworse':True},
         'changes_inside_mesh_boolean_operation':True,'Python_mesh_maintenance':False}
(here/'10-隔离内核候选源码准备清单.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n','utf8')
print('三份内部生成源码已准备',flush=True)
