"""依据孔源准确体积诊断修订近共面分组，并限制边界尝试到可改善的区域。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json

here=Path(__file__).resolve().parent
source=here/'第八轮差面边界触发与内部改善保留'
output=here/'第九轮机器精度共面与原平面有界生成';output.mkdir()
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
prior=json.loads((here/'125-差面边界触发与内部改善保留源码清单.json').read_text('utf8'))
for name,digest in prior['files'].items():
    assert sha(source/name)==digest
    (output/name).write_bytes((source/name).read_bytes())
path=output/'mesh_surface_intersection_internal.cpp';text=path.read_text('utf8')
old='''        if((N12.x.sign()!=ZERO) || (N12.y.sign()!=ZERO) ||(N12.z.sign()!=ZERO)) {
            return false;
        }'''
new='''        if((N12.x.sign()!=ZERO) || (N12.y.sign()!=ZERO) ||(N12.z.sign()!=ZERO)) {
            // 保存坐标造成的机器尺度非共面可单独核对；真实曲率和厚度不依靠角度容差合并。
            vec3 n1(N1.x.estimate(),N1.y.estimate(),N1.z.estimate());
            vec3 n2(N2.x.estimate(),N2.y.estimate(),N2.z.estimate());
            double l1=length(n1),l2=length(n2);
            if(!std::isfinite(l1) || !std::isfinite(l2) || l1==0.0 || l2==0.0) return false;
            n1/=l1;n2/=l2;
            double angle=std::atan2(length(cross(n1,n2)),std::abs(dot(n1,n2)))*180.0/M_PI;
            if(angle>1e-5) return false;
            const vec3 points[6]={p1,p2,p3,q1,q2,q3};
            double scale=0.0,residual=0.0;
            for(const vec3& p:points) {
                for(coord_index_t d=0;d<3;++d) scale=std::max(scale,std::abs(p[d]));
                scale=std::max(scale,length(p-p1));
                residual=std::max(residual,std::abs(dot(p-p1,n1)));
                residual=std::max(residual,std::abs(dot(p-q1,n2)));
            }
            return residual<=128.0*std::numeric_limits<double>::epsilon()*scale;
        }'''
assert text.count(old)==1;text=text.replace(old,new)
old='''                        facet_group_[f2] = facet_group_[f1];
                        f_visited_[f2] = true;'''
new='''                        // 所有传播面再与本组原种子核对，禁止机器误差沿长邻接链累计成曲面合并。
                        if(I_.get_initial_facet(f2)!=I_.get_initial_facet(f)) {
                            auto [p1,p2,p3]=I_.get_initial_facet_vertices(f);
                            auto [q1,q2,q3]=I_.get_initial_facet_vertices(f2);
                            if(!triangles_are_coplanar(p1,p2,p3,q1,q2,q3)) continue;
                        }
                        facet_group_[f2] = facet_group_[f1];
                        f_visited_[f2] = true;'''
assert text.count(old)==1;text=text.replace(old,new)
old='''    ExactPoint a=I_.exact_vertex(mesh_.facets.vertex(facets_[0],0));
    ExactPoint b=I_.exact_vertex(mesh_.facets.vertex(facets_[0],1));
    ExactPoint c=I_.exact_vertex(mesh_.facets.vertex(facets_[0],2));'''
new='''    // 使用原输入支撑平面，避免从已经生成的准确点再次构造高阶齐次系数。
    auto [plane_a,plane_b,plane_c]=I_.get_initial_facet_vertices(facets_[0]);
    ExactPoint a(plane_a.x,plane_a.y,plane_a.z,1.0);
    ExactPoint b(plane_b.x,plane_b.y,plane_b.z,1.0);
    ExactPoint c(plane_c.x,plane_c.y,plane_c.z,1.0);'''
assert text.count(old)==1;text=text.replace(old,new)
old='''    // 内部点未能改善的有效差面也允许一次有界边界细化，不能放松最终质量判定。
    if(!valid && allow_boundary && !boundary_attempt && after_score_computed && after.valid && after.bad>0) {'''
new='''    // 角点至少达到生成目标的四边形，内部点不能改善时才追加一次共边尝试。
    bool regular_quad=(ids.size()==4 && segments.size()==8);
    vector<vector<int>> neighbors(ids.size());
    if(regular_quad) {
        for(index_t i=0;i<segments.size();i+=2) {
            neighbors[segments[i]].push_back(segments[i+1]);neighbors[segments[i+1]].push_back(segments[i]);
        }
        for(index_t i=0;i<ids.size();++i) {
            if(neighbors[i].size()!=2) {regular_quad=false;break;}
            vec3 a=xyz[neighbors[i][0]]-xyz[i],b=xyz[neighbors[i][1]]-xyz[i];
            double angle=std::atan2(length(cross(a,b)),dot(a,b))*180.0/M_PI;
            if(angle<20.0) regular_quad=false;
        }
    }
    // 其余区域只保留第七轮已经证明有用的数量改善、面积拒绝触发，防止全面铺开额外成本。
    if(!valid && allow_boundary && !boundary_attempt && after_score_computed && after.valid && after.bad>0 &&
       (regular_quad || (after.bad<before.bad && after.area>before.area))) {'''
assert text.count(old)==1;text=text.replace(old,new);path.write_text(text,'utf8')
record={'生成时间':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),
        '修改时间及修改内容':'机器尺度共面、种子传播限制、原输入平面提升及受限四边形边界尝试',
        '文档概述':'孔源768非准确共面对诊断驱动的新原生候选；未经评价不计成功',
        '索引目录':['files'],'status':'prepared_ninth_machine_planarity_and_bounded_original_plane_generation',
        'files':{p.name:sha(p) for p in output.iterdir()},'prior_manifest_sha256':sha(here/'125-差面边界触发与内部改善保留源码清单.json'),
        'diagnosis_sha256':sha(here/'143-孔源差面相邻共面精度诊断结果.json'),
        'internal_point_budget':64,'boundary_attempt_budget':128,'neighbor_internal_budget':128,'neighbor_passes_max':1,
        'machine_planarity_margin':'128 times double epsilon times local edge and coordinate magnitude; also fixed-seed check',
        'long_runtime_cause_claim':'not established; prior address samples show CDT predicate cache insertion, not Triangle'}
(here/'147-机器尺度共面与原平面生成源码清单.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n','utf8')
builder=(here/'126-内部改善保留原生独立编译.py').read_text('utf8').replace('第八轮','第九轮')
(here/'148-机器尺度共面原生独立编译.py').write_text(builder,'utf8')
controller=(here/'127-内部改善保留原生编译上传执行.py').read_text('utf8')
for old,new in [('第八轮','第九轮'),('20261006_09','20261006_10'),
                ('125-差面边界触发与内部改善保留源码清单.json','147-机器尺度共面与原平面生成源码清单.json'),
                ('第九轮差面边界触发与内部改善保留','第九轮机器精度共面与原平面有界生成'),
                ('126-内部改善保留原生独立编译.py','148-机器尺度共面原生独立编译.py'),
                ('128-内部改善保留实际编译执行记录.json','150-机器尺度共面实际编译执行记录.json'),
                ('129-内部改善保留实际编译控制台日志.txt','151-机器尺度共面实际编译控制台日志.txt'),
                ('130-内部改善保留实际原生编译记录.json','152-机器尺度共面实际原生编译记录.json')]:controller=controller.replace(old,new)
(here/'149-机器尺度共面原生编译上传执行.py').write_text(controller,'utf8')
print('机器尺度共面及原平面有界生成源码已准备')
