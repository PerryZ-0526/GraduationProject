"""用实际共边短段诊断设计有界条带生成，保留旧内核和所有负结果。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json

here=Path(__file__).resolve().parent
source=here/'第十轮种子分组与边界一致生成'
output=here/'第十二轮一致二分共边条带生成';output.mkdir()
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
prior_path=here/'154-种子分组与边界一致生成源码清单.json'
prior=json.loads(prior_path.read_text('utf8'))
for name,digest in prior['files'].items():
    assert sha(source/name)==digest
    (output/name).write_bytes((source/name).read_bytes())
path=output/'mesh_surface_intersection_internal.cpp';code=path.read_text('utf8')
anchor='''    // 每条约束段使用独立标记，返回子段据此归回同一准确原边。'''
fast=r'''    // 对细长凸四边形直接生成一致二分条带，避免两个区域各自浮点补点造成近重复共边。
    if(allow_boundary && !boundary_attempt && ids.size()==4 && segments.size()==8) {
        vector<vector<int>> adjacent(4);
        for(index_t i=0;i<segments.size();i+=2) {
            adjacent[segments[i]].push_back(segments[i+1]);adjacent[segments[i+1]].push_back(segments[i]);
        }
        bool quad=true;
        for(const auto& neighbors:adjacent) quad=quad && neighbors.size()==2;
        int q[4]={0,0,0,0};
        if(quad) {
            q[1]=adjacent[q[0]][0];
            q[2]=adjacent[q[1]][0]==q[0] ? adjacent[q[1]][1] : adjacent[q[1]][0];
            q[3]=adjacent[q[2]][0]==q[1] ? adjacent[q[2]][1] : adjacent[q[2]][0];
            quad=q[3]!=q[0] && (adjacent[q[3]][0]==q[0] || adjacent[q[3]][1]==q[0]);
        }
        int longest=0;
        if(quad) for(int i=1;i<4;++i) {
            if(length(xyz[q[(i+1)%4]]-xyz[q[i]])>length(xyz[q[(longest+1)%4]]-xyz[q[longest]])) longest=i;
        }
        int ordered[4];for(int i=0;i<4;++i) ordered[i]=q[(longest+i)%4];
        double short_length=std::min(length(xyz[ordered[2]]-xyz[ordered[1]]),length(xyz[ordered[0]]-xyz[ordered[3]]));
        double long_length=std::max(length(xyz[ordered[1]]-xyz[ordered[0]]),length(xyz[ordered[2]]-xyz[ordered[3]]));
        for(int i=0;quad && i<4;++i) {
            vec3 a=xyz[ordered[(i+3)%4]]-xyz[ordered[i]],b=xyz[ordered[(i+1)%4]]-xyz[ordered[i]];
            double corner=std::atan2(length(cross(a,b)),dot(a,b))*180.0/M_PI;
            quad=corner>=20.0;
            int ia=ordered[i],ib=ordered[(i+1)%4],ic=ordered[(i+2)%4];
            double turn=(xy[2*ib]-xy[2*ia])*(xy[2*ic+1]-xy[2*ib+1])-(xy[2*ib+1]-xy[2*ia+1])*(xy[2*ic]-xy[2*ib]);
            int ja=ordered[0],jb=ordered[1],jc=ordered[2];
            double first_turn=(xy[2*jb]-xy[2*ja])*(xy[2*jc+1]-xy[2*jb+1])-(xy[2*jb+1]-xy[2*ja+1])*(xy[2*jc]-xy[2*jb]);
            quad=quad && turn*first_turn>0.0;
        }
        // 两条长边使用二分参数；不同区域请求不同层级时，边点集合仍为包含关系。
        index_t slices=1;
        double needed=short_length>0.0 ? long_length/short_length*std::tan(15.0*M_PI/180.0) : 1e20;
        while(slices<64 && double(slices)<needed) slices*=2;
        quad=quad && needed<=64.0 && long_length>3.0*short_length && slices>1;
        if(quad) {
            vector<ExactPoint> points;
            vector<std::pair<index_t,index_t>> edges;
            vector<vec3> positions=xyz;
            vector<int> strip;
            int previous[2]={ordered[0],ordered[3]};
            for(index_t step=1;step<=slices;++step) {
                int current[2];
                for(int side=0;side<2;++side) {
                    int start=side==0 ? ordered[0] : ordered[3];
                    int end=side==0 ? ordered[1] : ordered[2];
                    if(step==slices) {current[side]=end;continue;}
                    index_t va=ids[start],vb=ids[end];double t=double(step)/double(slices);
                    if(va>vb) {std::swap(va,vb);t=1.0-t;}
                    ExactPoint pa=I_.exact_vertex(va),pb=I_.exact_vertex(vb),p;
                    p.w=pa.w*pb.w;
                    for(coord_index_t d=0;d<3;++d) p[d]=pa[d]*pb.w*(1.0-t)+pb[d]*pa.w*t;
                    Numeric::optimize_number_representation(p);
                    current[side]=int(positions.size());positions.push_back(PCK::approximate(p));
                    points.push_back(p);edges.push_back({va,vb});
                }
                for(int v:{previous[0],current[0],current[1],previous[0],current[1],previous[1]}) strip.push_back(v);
                previous[0]=current[0];previous[1]=current[1];
            }
            Score generated=score(positions,strip);
            if(generated.valid && generated.bad<=before.bad && generated.area<=before.area &&
               (generated.bad<before.bad || generated.area<before.area)) {
                double generated_orientation=(xy[2*ordered[1]]-xy[2*ordered[0]])*(xy[2*ordered[2]+1]-xy[2*ordered[0]+1])-
                    (xy[2*ordered[1]+1]-xy[2*ordered[0]+1])*(xy[2*ordered[2]]-xy[2*ordered[0]]);
                const index_t original_vertices=mesh_.vertices.nb();
                for(index_t i=0;i<strip.size();i+=3) {
                    if(generated_orientation*orientation<0.0) std::swap(strip[i+1],strip[i+2]);
                    for(index_t k=0;k<3;++k) {
                        index_t v=index_t(strip[i+k]);triangles.push_back(v<ids.size() ? ids[v] : original_vertices+v-ids.size());
                    }
                }
                new_points.swap(points);boundary_edges.swap(edges);
                if(std::getenv("GEO_NATIVE_QUALITY_TRACE")!=nullptr) {
                    Logger::out("QualityStrip") << "group=" << group_id_ << " slices=" << slices
                        << " before_bad=" << before.bad << " after_bad=" << generated.bad << std::endl;
                }
                return true;
            }
        }
    }

'''
assert code.count(anchor)==1
code=code.replace(anchor,fast+anchor)
# 机器尺度合并只开放给共享原边的凸四边形，避免一般CT近共面组改变官方CDT质量。
anchor='''            return residual<=128.0*std::numeric_limits<double>::epsilon()*scale;'''
restricted=r'''            if(residual>128.0*std::numeric_limits<double>::epsilon()*scale) return false;
            // 非准确共面只允许原相邻三角形组成凸四边形，禁止扩展为一般曲面组。
            const vec3 left[3]={p1,p2,p3},right[3]={q1,q2,q3};
            int shared_left[2],shared_count=0,opposite_left=-1,opposite_right=-1;
            for(int i=0;i<3;++i) {
                bool common=false;
                for(int j=0;j<3;++j) common=common || (left[i].x==right[j].x && left[i].y==right[j].y && left[i].z==right[j].z);
                if(common) {if(shared_count>=2) return false;shared_left[shared_count++]=i;} else opposite_left=i;
            }
            for(int j=0;j<3;++j) {
                bool common=false;
                for(int i=0;i<3;++i) common=common || (left[i].x==right[j].x && left[i].y==right[j].y && left[i].z==right[j].z);
                if(!common) {if(opposite_right!=-1) return false;opposite_right=j;}
            }
            if(shared_count!=2 || opposite_left<0 || opposite_right<0) return false;
            vec3 corners[4]={left[shared_left[0]],left[opposite_left],left[shared_left[1]],right[opposite_right]};
            double previous_turn=0.0;
            for(int i=0;i<4;++i) {
                vec3 a=corners[(i+3)%4]-corners[i],b=corners[(i+1)%4]-corners[i];
                if(std::atan2(length(cross(a,b)),dot(a,b))*180.0/M_PI<20.0) return false;
                double turn=dot(cross(b,corners[(i+2)%4]-corners[(i+1)%4]),n1);
                if(turn==0.0 || (i>0 && turn*previous_turn<=0.0)) return false;
                previous_turn=turn;
            }
            return true;'''
assert code.count(anchor)==1
path.write_text(code.replace(anchor,restricted),'utf8')
now=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
manifest=here/'185-一致二分共边条带生成源码清单.json'
manifest.write_text(json.dumps({'生成时间':now,'修改时间及修改内容':now+'，首次新增同边一致二分条带',
 '文档概述':'最多64条带、126新增边点；局部与整体质量检查不放宽；待真实输出和耗时验证',
 '索引目录':['files','changes'],'prior_manifest_sha256':sha(prior_path),
 'files':{name:sha(output/name) for name in prior['files']},
 'changes':['规则细长凸四边形跳过浮点竞争补点','边端点按全局编号一致排序后二分插值','机器尺度分组限制为原边凸四边形']},ensure_ascii=False,indent=2)+'\n','utf8')
builder=(here/'155-种子分组与边界一致原生独立编译.py').read_text('utf8').replace('第十轮','第十二轮')
(here/'186-一致二分共边条带原生独立编译.py').write_text(builder,'utf8')
controller=(here/'156-种子分组与边界一致编译上传执行.py').read_text('utf8')
for a,b in [('20261006_11','20261006_13'),('第十轮种子分组与边界一致生成',output.name),
 ('154-种子分组与边界一致生成源码清单.json',manifest.name),
 ('155-种子分组与边界一致原生独立编译.py','186-一致二分共边条带原生独立编译.py'),
 ('157-种子分组与边界一致实际编译执行记录.json','188-一致二分共边实际编译执行记录.json'),
 ('158-种子分组与边界一致实际编译控制台日志.txt','189-一致二分共边实际编译控制台日志.txt'),
 ('159-种子分组与边界一致实际原生编译记录.json','190-一致二分共边实际原生编译记录.json'),
 ('第十轮','第十二轮')]:controller=controller.replace(a,b)
(here/'187-一致二分共边条带编译上传执行.py').write_text(controller,'utf8')
print('prepared_bounded_consistent_shared_edge_strip_generation')
