// 原精确拓扑和包围盒保留；相交仅用实际binary64点上的过滤精确谓词，不构造新交点。
#include "exact_mesh_memory.cpp"
#include <CGAL/Exact_predicates_inexact_constructions_kernel.h>
#include <algorithm>
#include <array>
#include <cstring>
#include <unordered_map>
#include <CGAL/boost/graph/Euler_operations.h>

using PredicateKernel = CGAL::Exact_predicates_inexact_constructions_kernel;
// 读取同次原始坐标，不把计算得到的近似交点送回谓词；段和三角形仅封装输入点。
struct PredicatePointMap {
    using key_type=Mesh::Vertex_index;
    using value_type=PredicateKernel::Point_3;
    using reference=value_type;
    using category=boost::readable_property_map_tag;
    const double* coordinates;
    friend value_type get(const PredicatePointMap& map,key_type vertex) {
        const double* p=map.coordinates+3*vertex.idx();
        return value_type(p[0],p[1],p[2]);
    }
};
using PointKey = std::array<std::uint64_t,3>;
using FaceKey = std::array<std::uint64_t,3>;
struct KeyHash {
    std::size_t operator()(const PointKey& key) const {
        std::size_t h=0;
        for(auto x:key) h^=std::hash<std::uint64_t>{}(x)+0x9e3779b9+(h<<6)+(h>>2);
        return h;
    }
};
static PointKey point_key(const double* p) {
    PointKey key;
    for(int k=0;k<3;++k) {
        // 正负零是同一个几何点；其他有限binary64值逐位匹配，不设置容差。
        double value=p[k]==0 ? 0 : p[k];std::memcpy(&key[k],&value,sizeof(value));
    }
    return key;
}
static FaceKey face_key(FaceKey key) {
    FaceKey a{key[1],key[2],key[0]},b{key[2],key[0],key[1]};
    return std::min(key,std::min(a,b));
}
struct VerifiedState {
    std::unordered_map<PointKey,std::int64_t,KeyHash> points;
    std::vector<double> coordinates;
    std::vector<std::int64_t> facets;
    std::vector<std::array<double,6>> bounds;
    std::vector<CGAL::Bbox_3> transition_boxes;
    Mesh certified_mesh;
    static std::array<double,6> face_bounds(const double* v,const std::int64_t* f) {
        std::array<double,6> box;
        for(int k=0;k<3;++k) {
            box[k]=std::min(v[3*f[0]+k],std::min(v[3*f[1]+k],v[3*f[2]+k]));
            box[k+3]=std::max(v[3*f[0]+k],std::max(v[3*f[1]+k],v[3*f[2]+k]));
        }
        return box;
    }
    VerifiedState(const double* v,std::uint64_t nv,const std::int64_t* f,std::uint64_t nf,Mesh* checked_mesh=nullptr)
        :coordinates(v,v+3*nv),facets(f,f+3*nf) {
        points.reserve(nv*2);
        for(std::uint64_t i=0;i<nv;++i) {
            auto insertion=points.emplace(point_key(v+3*i),i);
            if(!insertion.second) insertion.first->second=-1;
        }
        // 保存实际通过核查的拓扑；切削转换直接移交已构建网格，根证书仅启动时重建一次。
        if(checked_mesh) certified_mesh=std::move(*checked_mesh);
        else {
            for(std::uint64_t i=0;i<nv;++i) certified_mesh.add_vertex(Kernel::Point_3(v[3*i],v[3*i+1],v[3*i+2]));
            for(std::uint64_t i=0;i<nf;++i) certified_mesh.add_face(Mesh::Vertex_index(f[3*i]),Mesh::Vertex_index(f[3*i+1]),Mesh::Vertex_index(f[3*i+2]));
        }
        // 根证书启动时保存原谓词使用的包围盒，后续不得用更窄的近似盒替代它。
        transition_boxes.reserve(nf);bounds.reserve(nf);
        for(std::uint64_t i=0;i<nf;++i) {
            const auto* tri=f+3*i;
            auto box=certified_mesh.point(Mesh::Vertex_index(tri[0])).bbox()+
                certified_mesh.point(Mesh::Vertex_index(tri[1])).bbox()+certified_mesh.point(Mesh::Vertex_index(tri[2])).bbox();
            transition_boxes.push_back(box);bounds.push_back(face_bounds(v,tri));
        }
    }
    // 同一次转换中已建立的唯一点映射和盒子直接移交，避免再次哈希全部点和全部面。
    VerifiedState(const double* v,std::uint64_t nv,const std::int64_t* f,std::uint64_t nf,
                  std::unordered_map<PointKey,std::int64_t,KeyHash>&& prepared_points,
                  std::vector<CGAL::Bbox_3>&& prepared_boxes,Mesh&& checked_mesh)
        :points(std::move(prepared_points)),coordinates(v,v+3*nv),facets(f,f+3*nf),
         transition_boxes(std::move(prepared_boxes)),certified_mesh(std::move(checked_mesh)) {
        bounds.reserve(nf);
        for(std::uint64_t i=0;i<nf;++i) bounds.push_back(face_bounds(v,f+3*i));
    }
};
// 导出标记沿用完整核查接口，Linux与Windows仍使用相同证书逻辑。
EXACT_MEMORY_API void release_verified_state(void* state) {
    delete static_cast<VerifiedState*>(state);
}
EXACT_MEMORY_API void* create_verified_state(
    const double* v,std::uint64_t nv,const std::int64_t* f,std::uint64_t nf,
    std::int64_t* result,double* timings) {
    // 根证书只能由真实完整精确核查生成，不能由Python传入一个成功标志。
    if(audit_arrays(v,nv,f,nf,result,timings)!=0 || !result[6]) return nullptr;
    try {return new VerifiedState(v,nv,f,nf);} catch(...) {return nullptr;}
}
EXACT_MEMORY_API int audit_transition(
    const void* parent,const double* v,std::uint64_t nv,const std::int64_t* f,
    std::uint64_t nf,std::int64_t* result,double* timings,void** next_state) {
    try {
        if(!parent) return 1;
        *next_state=nullptr;for(int i=0;i<12;++i) result[i]=0;
        const auto& verified=*static_cast<const VerifiedState*>(parent);
        auto start=Clock::now();Mesh mesh;std::vector<Mesh::Vertex_index> vertices;
        vertices.reserve(nv);
        std::unordered_map<PointKey,std::int64_t,KeyHash> current_points;current_points.reserve(nv*2);
        for(std::uint64_t i=0;i<nv;++i) {
            const double* p=v+3*i;
            for(int k=0;k<3;++k) if(!std::isfinite(p[k])) return 1;
            // 别名仍标记为不可继承，索引只用于同次转换的唯一坐标。
            auto insertion=current_points.emplace(point_key(p),i);
            if(!insertion.second) insertion.first->second=-1;
        }
        std::vector<std::int64_t> point_parent(nv,-1);
        for(std::uint64_t i=0;i<nv;++i) {
            auto key=point_key(v+3*i);auto old=verified.points.find(key);
            // 几何坐标出现别名时不继承，避免共享顶点身份变化漏掉相交。
            if(current_points.at(key)>=0 && old!=verified.points.end() && old->second>=0)
                point_parent[i]=old->second;
            // 复用原精确数值对象；仅新点从实际binary64输入重新构造。
            vertices.push_back(mesh.add_vertex(point_parent[i]>=0 ?
                verified.certified_mesh.point(Mesh::Vertex_index(point_parent[i])) :
                Kernel::Point_3(v[3*i],v[3*i+1],v[3*i+2])));
        }
        std::vector<bool> inherited(nf,false);
        std::vector<Mesh::Face_index> inherited_faces(nf,Mesh::null_face());
        std::vector<Mesh::Face_index> face_ids;face_ids.reserve(nf);
        for(std::uint64_t i=0;i<nf;++i) {
            const auto* tri=f+3*i;
            for(int k=0;k<3;++k) if(tri[k]<0 || std::uint64_t(tri[k])>=nv) return 1;
            auto face=mesh.add_face(vertices[tri[0]],vertices[tri[1]],vertices[tri[2]]);
            if(face==Mesh::null_face()) {result[0]=1;return 0;}
            face_ids.push_back(face);
            if(point_parent[tri[0]]>=0 && point_parent[tri[1]]>=0 && point_parent[tri[2]]>=0) {
                // 已认证拓扑自身裁决同方向三角面的身份，不再另存全网格面哈希。
                const auto& old_mesh=verified.certified_mesh;
                auto edge=old_mesh.halfedge(Mesh::Vertex_index(point_parent[tri[0]]),Mesh::Vertex_index(point_parent[tri[1]]));
                if(edge!=Mesh::null_halfedge() && old_mesh.face(edge)!=Mesh::null_face() &&
                   old_mesh.target(old_mesh.next(edge))==Mesh::Vertex_index(point_parent[tri[2]])) {
                    inherited[i]=true;inherited_faces[i]=old_mesh.face(edge);
                }
            }
        }
        timings[0]=milliseconds(start);start=Clock::now();
        using Box=CGAL::Box_intersection_d::Box_with_info_d<double,3,Mesh::Face_index,CGAL::Box_intersection_d::ID_FROM_BOX_ADDRESS>;
        std::vector<Box> boxes;boxes.reserve(nf);std::int64_t degenerate=0;
        std::vector<CGAL::Bbox_3> prepared_boxes;prepared_boxes.reserve(nf);
        for(std::uint64_t i=0;i<nf;++i) {
            if(inherited[i]) {
                // 唯一点与有向原面均逐位继承，非共线性由父证书承担，原盒完整保留。
                auto box=verified.transition_boxes[inherited_faces[i].idx()];
                prepared_boxes.push_back(box);boxes.emplace_back(box,face_ids[i]);continue;
            }
            const auto* tri=f+3*i;
            auto &a=mesh.point(vertices[tri[0]]),&b=mesh.point(vertices[tri[1]]),&c=mesh.point(vertices[tri[2]]);
            auto box=a.bbox()+b.bbox()+c.bbox();prepared_boxes.push_back(box);
            if(CGAL::collinear(a,b,c)) {++degenerate;continue;}
            boxes.emplace_back(box,face_ids[i]);
        }
        timings[1]=milliseconds(start);start=Clock::now();
        // 直接查询变化面与原面、变化面与变化面，连未变面的盒子对也不再枚举。
        std::vector<const Box*> old_boxes,new_boxes;
        old_boxes.reserve(boxes.size());new_boxes.reserve(boxes.size());
        for(auto& box:boxes) (inherited[box.info().idx()] ? old_boxes : new_boxes).push_back(&box);
        // 精确谓词的过滤只加速符号判断，无法过滤时由CGAL回到精确算术。
        PredicatePointMap map{v};PredicateKernel kernel;
        std::int64_t pairs=0,checked=0,skipped=0;
        auto callback=[&](const Box* a,const Box* b) {
            auto i=a->info().idx(),j=b->info().idx();
            if(inherited[i] && inherited[j]) {++skipped;return;}
            ++checked;
            if(CGAL::Polygon_mesh_processing::internal::do_faces_intersect<PredicateKernel>(
                halfedge(a->info(),mesh),halfedge(b->info(),mesh),mesh,map,
                kernel.construct_segment_3_object(),kernel.construct_triangle_3_object(),kernel.do_intersect_3_object())) ++pairs;
        };
        // 明确使用ptrdiff_t截止参数，避免被CGAL泛型重载误判为盒子Traits。
        CGAL::box_intersection_d<CGAL::Sequential_tag>(new_boxes.begin(),new_boxes.end(),old_boxes.begin(),old_boxes.end(),callback,std::ptrdiff_t(2000));
        CGAL::box_self_intersection_d<CGAL::Sequential_tag>(new_boxes.begin(),new_boxes.end(),callback,std::ptrdiff_t(2000));
        timings[2]=milliseconds(start);start=Clock::now();
        bool closed=CGAL::is_closed(mesh);
        result[0]=1;result[1]=1;result[2]=nv;result[3]=nf;result[4]=closed;
        result[5]=pairs+degenerate;result[7]=degenerate;
        result[8]=std::count(inherited.begin(),inherited.end(),true);result[9]=checked;result[10]=skipped;
        result[6]=closed && !pairs && !degenerate && nf>0;
        // 新缓存必须来自同次精确核查的实际对象，不能再次读另一份可变输入。
        if(result[6]) *next_state=new VerifiedState(v,nv,f,nf,std::move(current_points),std::move(prepared_boxes),std::move(mesh));
        timings[3]=milliseconds(start);
        return 0;
    } catch(...) {return 2;}
}

EXACT_MEMORY_API int audit_fixed_flips(
    void* parent,const double* v,std::uint64_t nv,const std::int64_t* final_faces,std::uint64_t nf,
    const std::int64_t* operations,std::uint64_t count,std::int64_t* result,double* timings) {
    try {
        for(int k=0;k<12;++k) result[k]=0;
        if(!parent || count>16) return 1;
        auto& verified=*static_cast<VerifiedState*>(parent);auto start=Clock::now();
        auto reject=[&](std::int64_t reason) {result[11]=reason;return 0;};
        if(verified.coordinates.size()!=3*nv || verified.facets.size()!=3*nf ||
           std::memcmp(v,verified.coordinates.data(),3*nv*sizeof(double))!=0) return reject(1);
        // 使用私有拓扑副本完成整个事务；任一失效记录或碰撞不能污染原父证书。
        Mesh mesh=verified.certified_mesh;auto facets=verified.facets;auto bounds=verified.bounds;
        // 包围盒也使用私有事务副本，失败记录不能污染后续转换的父几何缓存。
        auto transition_boxes=verified.transition_boxes;
        timings[0]=milliseconds(start);start=Clock::now();
        // 翻边碰撞使用同一原坐标谓词；固定点逐位检查和私有拓扑事务仍保持。
        PredicateKernel kernel;PredicatePointMap map{v};
        std::uint64_t checked=0;
        auto tri_key=[](const std::int64_t* f) {return face_key(FaceKey{std::uint64_t(f[0]),std::uint64_t(f[1]),std::uint64_t(f[2])});};
        auto intersects=[&](std::uint64_t i,std::uint64_t j) {
            ++checked;
            return CGAL::Polygon_mesh_processing::internal::do_faces_intersect<PredicateKernel>(
                halfedge(Mesh::Face_index(i),mesh),halfedge(Mesh::Face_index(j),mesh),mesh,map,
                kernel.construct_segment_3_object(),kernel.construct_triangle_3_object(),kernel.do_intersect_3_object());
        };
        for(std::uint64_t q=0;q<count;++q) {
            result[8]=q;
            const auto* op=operations+14*q;auto i=op[0],j=op[1];
            if(i<0 || j<0 || std::uint64_t(i)>=nf || std::uint64_t(j)>=nf || i==j) return reject(2);
            if(std::memcmp(facets.data()+3*i,op+2,3*sizeof(std::int64_t)) ||
               std::memcmp(facets.data()+3*j,op+5,3*sizeof(std::int64_t))) return reject(3);
            std::int64_t a=-1,b=-1,c=-1,d=-1;
            // 只接受两面拥有相反方向的共同边，四点互异且新对角线在全图中不存在。
            for(int k=0;k<3;++k) for(int t=0;t<3;++t)
                if(op[2+k]==op[5+(t+1)%3] && op[2+(k+1)%3]==op[5+t]) {
                    a=op[2+k];b=op[2+(k+1)%3];c=op[2+(k+2)%3];d=op[5+(t+2)%3];
                }
            if(a<0 || c==d || a==b || c==a || c==b || d==a || d==b) return reject(4);
            auto edge=mesh.halfedge(Mesh::Vertex_index(a),Mesh::Vertex_index(b));
            if(edge==Mesh::null_halfedge() || mesh.face(edge)!=Mesh::Face_index(i) ||
               mesh.face(mesh.opposite(edge))!=Mesh::Face_index(j) ||
               mesh.halfedge(Mesh::Vertex_index(c),Mesh::Vertex_index(d))!=Mesh::null_halfedge()) return reject(5);
            const std::int64_t expected[6]={c,d,b,d,c,a};
            if(tri_key(op+8)!=tri_key(expected) || tri_key(op+11)!=tri_key(expected+3)) return reject(6);
            for(int k=0;k<6;++k) if(op[8+k]<0 || std::uint64_t(op[8+k])>=nv) return reject(7);
            for(int t=0;t<2;++t) {
                const auto* f=op+8+3*t;
                if(CGAL::collinear(mesh.point(Mesh::Vertex_index(f[0])),mesh.point(Mesh::Vertex_index(f[1])),mesh.point(Mesh::Vertex_index(f[2])))) return reject(8);
            }
            CGAL::Euler::flip_edge(edge,mesh);
            for(int t=0;t<2;++t) {
                auto id=t==0 ? i : j;auto h=mesh.halfedge(Mesh::Face_index(id));
                const std::int64_t actual[3]={mesh.source(h).idx(),mesh.target(h).idx(),mesh.target(mesh.next(h)).idx()};
                if(tri_key(actual)!=tri_key(op+8+3*t)) return reject(9);
                std::copy(op+8+3*t,op+11+3*t,facets.begin()+3*id);
                bounds[id]=VerifiedState::face_bounds(v,facets.data()+3*id);
                const auto* tri=facets.data()+3*id;
                transition_boxes[id]=mesh.point(Mesh::Vertex_index(tri[0])).bbox()+
                    mesh.point(Mesh::Vertex_index(tri[1])).bbox()+mesh.point(Mesh::Vertex_index(tri[2])).bbox();
            }
            // 全部远区仍是碰撞障碍。仅跳过父证书已经认证的旧面之间，不能删去外部网格。
            for(auto id:{i,j}) for(std::uint64_t other=0;other<nf;++other) {
                if(other==std::uint64_t(id) || (id==j && other==std::uint64_t(i))) continue;
                bool overlap=true;
                for(int k=0;k<3;++k) overlap=overlap && bounds[id][k]<=bounds[other][k+3] && bounds[other][k]<=bounds[id][k+3];
                if(overlap && intersects(id,other)) {result[2]=id;result[3]=other;result[9]=checked;return reject(10);}
            }
        }
        timings[1]=milliseconds(start);start=Clock::now();
        if(std::memcmp(final_faces,facets.data(),3*nf*sizeof(std::int64_t))) return reject(11);
        // Euler替换保留闭合流形；Surface_mesh核查允许源修复留下的无引用固定点，不增加输入门槛。
        if(!mesh.is_valid(false) || !CGAL::is_closed(mesh)) return reject(12);
        timings[2]=milliseconds(start);start=Clock::now();
        // 成功才一次性移交拓扑、实际面与几何缓存；不再维护重复的全图面哈希。
        verified.certified_mesh=std::move(mesh);verified.facets=std::move(facets);verified.bounds=std::move(bounds);
        verified.transition_boxes=std::move(transition_boxes);
        result[0]=1;result[1]=1;result[2]=nv;result[3]=nf;result[4]=1;result[6]=1;result[8]=count;result[9]=checked;
        timings[3]=milliseconds(start);return 0;
    } catch(...) {return 2;}
}
