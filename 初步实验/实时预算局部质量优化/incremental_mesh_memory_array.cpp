// 保留原完整认证及翻边事务；闭合源转换改用连续半边数组供原CGAL相交谓词读取。
#define create_verified_state create_surface_verified_state
#define release_verified_state release_surface_verified_state
#define audit_transition audit_surface_transition
#define audit_fixed_flips audit_surface_fixed_flips
#include "incremental_mesh_memory_filtered.cpp"
#undef create_verified_state
#undef release_verified_state
#undef audit_transition
#undef audit_fixed_flips
#include <memory>
#include <limits>

namespace ArrayTopology {
using Halfedge=std::uint64_t;
static constexpr Halfedge absent=std::numeric_limits<Halfedge>::max();
struct Graph {
    std::vector<std::int64_t> facets;
    std::vector<Halfedge> opposite_edges,table;
    bool closed_manifold=false;
    static Halfedge next_edge(Halfedge h) {return h/3*3+(h+1)%3;}
    static Halfedge prev_edge(Halfedge h) {return h/3*3+(h+2)%3;}
    std::uint64_t from(Halfedge h) const {return facets[h];}
    std::uint64_t to(Halfedge h) const {return facets[next_edge(h)];}
    static std::size_t hash(std::uint64_t a,std::uint64_t b) {
        // 哈希只定位槽位；发生冲突必须比较实际的两个顶点编号。
        std::uint64_t x=a*0x9e3779b97f4a7c15ULL+b;
        x=(x^(x>>30))*0xbf58476d1ce4e5b9ULL;
        x=(x^(x>>27))*0x94d049bb133111ebULL;return x^(x>>31);
    }
    Halfedge find(std::uint64_t a,std::uint64_t b) const {
        std::size_t slot=hash(a,b)&(table.size()-1);
        while(table[slot]!=absent) {
            auto h=table[slot];if(from(h)==a && to(h)==b) return h;
            slot=(slot+1)&(table.size()-1);
        }
        return absent;
    }
    void insert(Halfedge h) {
        std::size_t slot=hash(from(h),to(h))&(table.size()-1);
        while(table[slot]!=absent) slot=(slot+1)&(table.size()-1);
        table[slot]=h;
    }
    void erase(Halfedge edge) {
        std::size_t slot=hash(from(edge),to(edge))&(table.size()-1);
        while(table[slot]!=edge) slot=(slot+1)&(table.size()-1);
        table[slot]=absent;slot=(slot+1)&(table.size()-1);
        // 后移簇重新插入保持查找连续性，不遗留随多次质量更新积累的墓碑槽。
        while(table[slot]!=absent) {
            auto h=table[slot];table[slot]=absent;insert(h);slot=(slot+1)&(table.size()-1);
        }
    }
    bool valid_fans(std::uint64_t nv) const {
        std::vector<Halfedge> first(nv,absent);std::vector<std::uint64_t> degree(nv,0);
        for(Halfedge h=0;h<facets.size();++h) {
            auto a=from(h),b=to(h),op=opposite_edges[h];
            if(a>=nv || b>=nv || a==b || op>=facets.size() || opposite_edges[op]!=h || from(op)!=b || to(op)!=a) return false;
            first[a]=h;++degree[a];
        }
        for(std::uint64_t a=0;a<nv;++a) if(first[a]!=absent) {
            auto h=first[a];std::uint64_t count=0;
            do {if(from(h)!=a || ++count>degree[a]) return false;h=opposite_edges[prev_edge(h)];} while(h!=first[a]);
            if(count!=degree[a]) return false;
        }
        return !facets.empty();
    }
    bool replace_two_faces(std::uint64_t i,std::uint64_t j,const std::int64_t* after) {
        // 私有事务中先移除六条原有向边，再建立新边与外部半边的对应；失败对象不提交。
        for(auto face:{i,j}) for(int k=0;k<3;++k) erase(3*face+k);
        for(auto face:{i,j}) for(int k=0;k<3;++k) {
            auto h=3*face+k,op=opposite_edges[h];
            // 两面原共同边的另一半可能已清除，不能将空编号用作数组下标。
            if(op!=absent) opposite_edges[op]=absent;
            opposite_edges[h]=absent;
        }
        std::copy(after,after+3,facets.begin()+3*i);std::copy(after+3,after+6,facets.begin()+3*j);
        for(auto face:{i,j}) for(int k=0;k<3;++k) {
            auto h=3*face+k,a=from(h),b=to(h);
            if(find(a,b)!=absent) return false;
            auto op=find(b,a);
            if(op!=absent) {opposite_edges[h]=op;opposite_edges[op]=h;}
            insert(h);
        }
        for(auto face:{i,j}) for(int k=0;k<3;++k) if(opposite_edges[3*face+k]==absent) return false;
        return true;
    }
    Graph(const std::int64_t* f,std::uint64_t nf,std::uint64_t nv):facets(f,f+3*nf) {
        std::size_t capacity=1;while(capacity<6*nf+1) capacity*=2;
        table.assign(capacity,absent);opposite_edges.assign(3*nf,absent);
        std::vector<Halfedge> first(nv,absent);std::vector<std::uint64_t> degree(nv,0);
        for(Halfedge h=0;h<3*nf;++h) {
            auto a=from(h),b=to(h);
            if(a>=nv || b>=nv || a==b) return;
            auto same=find(a,b);if(same!=absent) return;
            auto reverse=find(b,a);
            if(reverse!=absent) {opposite_edges[h]=reverse;opposite_edges[reverse]=h;}
            std::size_t slot=hash(a,b)&(capacity-1);
            while(table[slot]!=absent) slot=(slot+1)&(capacity-1);
            table[slot]=h;first[a]=h;++degree[a];
        }
        for(auto h:opposite_edges) if(h==absent) return;
        // 每条边成对仍不足以证明流形；每个引用顶点的星形邻域必须恰为一个闭环。
        for(std::uint64_t a=0;a<nv;++a) if(first[a]!=absent) {
            auto h=first[a];std::uint64_t count=0;
            do {
                if(from(h)!=a || ++count>degree[a]) return;
                h=opposite_edges[prev_edge(h)];
            } while(h!=first[a]);
            if(count!=degree[a]) return;
        }
        closed_manifold=nf>0;
    }
};
inline Mesh::Vertex_index source(Halfedge h,const Graph& g) {return Mesh::Vertex_index(g.from(h));}
inline Mesh::Vertex_index target(Halfedge h,const Graph& g) {return Mesh::Vertex_index(g.to(h));}
inline Halfedge next(Halfedge h,const Graph&) {return Graph::next_edge(h);}
inline Halfedge opposite(Halfedge h,const Graph& g) {return g.opposite_edges[h];}
inline Mesh::Face_index face(Halfedge h,const Graph&) {return h==absent ? Mesh::null_face() : Mesh::Face_index(h/3);}
inline bool is_border(Halfedge h,const Graph&) {return h==absent;}
}
namespace boost {
template<> struct graph_traits<ArrayTopology::Graph> {
    using vertex_descriptor=Mesh::Vertex_index;
    using halfedge_descriptor=ArrayTopology::Halfedge;
    using face_descriptor=Mesh::Face_index;
};
}

struct ArrayVerifiedState {
    std::unordered_map<PointKey,std::int64_t,KeyHash> points;
    std::vector<double> coordinates;
    std::vector<Kernel::Point_3> exact_points;
    std::vector<CGAL::Bbox_3> boxes;
    ArrayTopology::Graph graph;
    mutable std::unique_ptr<VerifiedState> editable;
    // 初态保持完整EPECK根认证；启动时接受已认证对象，不由外部成功标志替代。
    explicit ArrayVerifiedState(std::unique_ptr<VerifiedState> root)
        :points(root->points),coordinates(root->coordinates),boxes(root->transition_boxes),
         graph(root->facets.data(),root->facets.size()/3,root->coordinates.size()/3),editable(std::move(root)) {
        exact_points.reserve(coordinates.size()/3);
        for(std::uint64_t i=0;i<coordinates.size()/3;++i) exact_points.push_back(editable->certified_mesh.point(Mesh::Vertex_index(i)));
        if(!graph.closed_manifold) throw std::runtime_error("根拓扑与闭合数组不一致");
    }
    ArrayVerifiedState(const double* v,std::uint64_t nv,ArrayTopology::Graph&& checked,
        std::unordered_map<PointKey,std::int64_t,KeyHash>&& prepared_points,
        std::vector<Kernel::Point_3>&& prepared_exact,std::vector<CGAL::Bbox_3>&& prepared_boxes)
        :points(std::move(prepared_points)),coordinates(v,v+3*nv),exact_points(std::move(prepared_exact)),
         boxes(std::move(prepared_boxes)),graph(std::move(checked)) {}
    VerifiedState& editing_mesh() const {
        // 真正需要可编辑拓扑时才建整张Surface_mesh；调用方总计时仍包含这一成本。
        if(!editable) editable=std::make_unique<VerifiedState>(coordinates.data(),coordinates.size()/3,graph.facets.data(),graph.facets.size()/3);
        return *editable;
    }
};
EXACT_MEMORY_API void release_verified_state(void* state) {delete static_cast<ArrayVerifiedState*>(state);}
EXACT_MEMORY_API void* create_verified_state(const double* v,std::uint64_t nv,const std::int64_t* f,std::uint64_t nf,
    std::int64_t* result,double* timings) {
    std::unique_ptr<VerifiedState> root(static_cast<VerifiedState*>(create_surface_verified_state(v,nv,f,nf,result,timings)));
    if(!root) return nullptr;
    try {return new ArrayVerifiedState(std::move(root));} catch(...) {return nullptr;}
}
EXACT_MEMORY_API int audit_transition(const void* parent,const double* v,std::uint64_t nv,const std::int64_t* f,
    std::uint64_t nf,std::int64_t* result,double* timings,void** next_state) {
    try {
        if(!parent) return 1;
        *next_state=nullptr;for(int i=0;i<12;++i) result[i]=0;
        const auto& verified=*static_cast<const ArrayVerifiedState*>(parent);
        auto start=Clock::now();
        // 范围及有限性先核查，不让非法编号进入半边表。
        for(std::uint64_t i=0;i<3*nv;++i) if(!std::isfinite(v[i])) return 1;
        for(std::uint64_t i=0;i<3*nf;++i) if(f[i]<0 || std::uint64_t(f[i])>=nv) return 1;
        ArrayTopology::Graph graph(f,nf,nv);
        if(!graph.closed_manifold) {
            // 开边界、重复边或分叉点保留原完整路径及拒绝语义，不用轻量检查擅自放行。
            void* next=nullptr;
            auto& original=verified.editing_mesh();double prepare_ms=milliseconds(start);
            int code=audit_surface_transition(&original,v,nv,f,nf,result,timings,&next);
            timings[0]+=prepare_ms;
            if(next) *next_state=new ArrayVerifiedState(std::unique_ptr<VerifiedState>(static_cast<VerifiedState*>(next)));
            return code;
        }
        std::unordered_map<PointKey,std::int64_t,KeyHash> current;current.reserve(nv*2);
        for(std::uint64_t i=0;i<nv;++i) {
            auto insertion=current.emplace(point_key(v+3*i),i);if(!insertion.second) insertion.first->second=-1;
        }
        std::vector<std::int64_t> point_parent(nv,-1);
        std::vector<Kernel::Point_3> exact;exact.reserve(nv);
        for(std::uint64_t i=0;i<nv;++i) {
            auto key=point_key(v+3*i);auto old=verified.points.find(key);
            // 同坐标别名不能继承顶点身份；新点保持原binary64到EPECK转换。
            if(current.at(key)>=0 && old!=verified.points.end() && old->second>=0) point_parent[i]=old->second;
            exact.push_back(point_parent[i]>=0 ? verified.exact_points[point_parent[i]] : Kernel::Point_3(v[3*i],v[3*i+1],v[3*i+2]));
        }
        std::vector<bool> inherited(nf,false);std::vector<std::uint64_t> old_faces(nf,0);
        for(std::uint64_t i=0;i<nf;++i) {
            const auto* tri=f+3*i;
            if(point_parent[tri[0]]<0 || point_parent[tri[1]]<0 || point_parent[tri[2]]<0) continue;
            auto edge=verified.graph.find(point_parent[tri[0]],point_parent[tri[1]]);
            if(edge!=ArrayTopology::absent && verified.graph.to(ArrayTopology::Graph::next_edge(edge))==std::uint64_t(point_parent[tri[2]])) {
                inherited[i]=true;old_faces[i]=edge/3;
            }
        }
        timings[0]=milliseconds(start);start=Clock::now();
        using Box=CGAL::Box_intersection_d::Box_with_info_d<double,3,Mesh::Face_index,CGAL::Box_intersection_d::ID_FROM_BOX_ADDRESS>;
        std::vector<Box> boxes;boxes.reserve(nf);std::vector<CGAL::Bbox_3> prepared;prepared.reserve(nf);std::int64_t degenerate=0;
        for(std::uint64_t i=0;i<nf;++i) {
            if(inherited[i]) {auto box=verified.boxes[old_faces[i]];prepared.push_back(box);boxes.emplace_back(box,Mesh::Face_index(i));continue;}
            const auto* tri=f+3*i;auto& a=exact[tri[0]];auto& b=exact[tri[1]];auto& c=exact[tri[2]];
            auto box=a.bbox()+b.bbox()+c.bbox();prepared.push_back(box);
            if(CGAL::collinear(a,b,c)) {++degenerate;continue;}
            boxes.emplace_back(box,Mesh::Face_index(i));
        }
        timings[1]=milliseconds(start);start=Clock::now();
        std::vector<const Box*> old_boxes,new_boxes;old_boxes.reserve(nf);new_boxes.reserve(nf);
        for(auto& box:boxes) (inherited[box.info().idx()] ? old_boxes : new_boxes).push_back(&box);
        PredicatePointMap map{v};PredicateKernel kernel;std::int64_t pairs=0,checked=0,skipped=0;
        auto callback=[&](const Box* a,const Box* b) {
            auto i=a->info().idx(),j=b->info().idx();
            if(inherited[i] && inherited[j]) {++skipped;return;}
            ++checked;
            // 图接口仅替换数据读取；相交判定仍调用原CGAL共享边、共享点和普通面逻辑。
            if(CGAL::Polygon_mesh_processing::internal::do_faces_intersect<PredicateKernel>(3*i,3*j,graph,map,
                kernel.construct_segment_3_object(),kernel.construct_triangle_3_object(),kernel.do_intersect_3_object())) ++pairs;
        };
        CGAL::box_intersection_d<CGAL::Sequential_tag>(new_boxes.begin(),new_boxes.end(),old_boxes.begin(),old_boxes.end(),callback,std::ptrdiff_t(2000));
        CGAL::box_self_intersection_d<CGAL::Sequential_tag>(new_boxes.begin(),new_boxes.end(),callback,std::ptrdiff_t(2000));
        timings[2]=milliseconds(start);start=Clock::now();
        result[0]=1;result[1]=1;result[2]=nv;result[3]=nf;result[4]=1;result[5]=pairs+degenerate;result[7]=degenerate;
        result[8]=std::count(inherited.begin(),inherited.end(),true);result[9]=checked;result[10]=skipped;
        result[6]=!pairs && !degenerate;
        // 已认证数据直接移交，成功源不在返回前后另建隐蔽的整张网格。
        if(result[6]) *next_state=new ArrayVerifiedState(v,nv,std::move(graph),std::move(current),std::move(exact),std::move(prepared));
        timings[3]=milliseconds(start);return 0;
    } catch(...) {return 2;}
}
EXACT_MEMORY_API int audit_fixed_flips(void* parent,const double* v,std::uint64_t nv,const std::int64_t* f,std::uint64_t nf,
    const std::int64_t* operations,std::uint64_t count,std::int64_t* result,double* timings) {
    try {
        if(!parent) return 1;
        auto& verified=*static_cast<ArrayVerifiedState*>(parent);
        if(count==0) {
            for(int k=0;k<12;++k) result[k]=0;
            // 零操作只核对实际数组恒等；不能为改变面但缺失操作记录的输入生成证书。
            if(verified.coordinates.size()!=3*nv || verified.graph.facets.size()!=3*nf ||
               std::memcmp(v,verified.coordinates.data(),3*nv*sizeof(double))) {result[11]=1;return 0;}
            if(std::memcmp(f,verified.graph.facets.data(),3*nf*sizeof(std::int64_t))) {result[11]=11;return 0;}
            result[0]=1;result[1]=1;result[2]=nv;result[3]=nf;result[4]=1;result[6]=1;return 0;
        }
        for(int k=0;k<12;++k) result[k]=0;
        if(count>16) return 1;
        auto reject=[&](std::int64_t reason) {result[11]=reason;return 0;};
        if(verified.coordinates.size()!=3*nv || verified.graph.facets.size()!=3*nf ||
           std::memcmp(v,verified.coordinates.data(),3*nv*sizeof(double))) return reject(1);
        auto start=Clock::now();auto graph=verified.graph;auto boxes=verified.boxes;
        std::vector<std::array<double,6>> bounds;bounds.reserve(nf);
        for(std::uint64_t i=0;i<nf;++i) bounds.push_back(VerifiedState::face_bounds(v,graph.facets.data()+3*i));
        timings[0]=milliseconds(start);start=Clock::now();
        PredicateKernel kernel;PredicatePointMap map{v};std::uint64_t checked=0;
        auto tri_key=[](const std::int64_t* tri) {return face_key(FaceKey{std::uint64_t(tri[0]),std::uint64_t(tri[1]),std::uint64_t(tri[2])});};
        auto intersects=[&](std::uint64_t i,std::uint64_t j) {
            ++checked;
            return CGAL::Polygon_mesh_processing::internal::do_faces_intersect<PredicateKernel>(3*i,3*j,graph,map,
                kernel.construct_segment_3_object(),kernel.construct_triangle_3_object(),kernel.do_intersect_3_object());
        };
        for(std::uint64_t q=0;q<count;++q) {
            result[8]=q;const auto* op=operations+14*q;auto i=op[0],j=op[1];
            if(i<0 || j<0 || std::uint64_t(i)>=nf || std::uint64_t(j)>=nf || i==j) return reject(2);
            if(std::memcmp(graph.facets.data()+3*i,op+2,3*sizeof(std::int64_t)) ||
               std::memcmp(graph.facets.data()+3*j,op+5,3*sizeof(std::int64_t))) return reject(3);
            std::int64_t a=-1,b=-1,c=-1,d=-1;
            // 与原Euler路径相同，要求相反共同边、四点互异及全图中不存在新对角线。
            for(int k=0;k<3;++k) for(int t=0;t<3;++t)
                if(op[2+k]==op[5+(t+1)%3] && op[2+(k+1)%3]==op[5+t]) {
                    a=op[2+k];b=op[2+(k+1)%3];c=op[2+(k+2)%3];d=op[5+(t+2)%3];
                }
            if(a<0 || c==d || a==b || c==a || c==b || d==a || d==b) return reject(4);
            auto edge=graph.find(a,b);
            if(edge==ArrayTopology::absent || edge/3!=std::uint64_t(i) || graph.opposite_edges[edge]/3!=std::uint64_t(j) ||
               graph.find(c,d)!=ArrayTopology::absent) return reject(5);
            const std::int64_t expected[6]={c,d,b,d,c,a};
            if(tri_key(op+8)!=tri_key(expected) || tri_key(op+11)!=tri_key(expected+3)) return reject(6);
            for(int k=0;k<6;++k) if(op[8+k]<0 || std::uint64_t(op[8+k])>=nv) return reject(7);
            for(int t=0;t<2;++t) {
                const auto* tri=op+8+3*t;
                if(CGAL::collinear(verified.exact_points[tri[0]],verified.exact_points[tri[1]],verified.exact_points[tri[2]])) return reject(8);
            }
            if(!graph.replace_two_faces(i,j,op+8)) return reject(9);
            for(auto id:{i,j}) {
                const auto* tri=graph.facets.data()+3*id;
                bounds[id]=VerifiedState::face_bounds(v,tri);
                boxes[id]=verified.exact_points[tri[0]].bbox()+verified.exact_points[tri[1]].bbox()+verified.exact_points[tri[2]].bbox();
            }
            // 继续遍历全部外部障碍；只认证两张新面相关的实际相交关系。
            for(auto id:{i,j}) for(std::uint64_t other=0;other<nf;++other) {
                if(other==std::uint64_t(id) || (id==j && other==std::uint64_t(i))) continue;
                bool overlap=true;
                for(int k=0;k<3;++k) overlap=overlap && bounds[id][k]<=bounds[other][k+3] && bounds[other][k]<=bounds[id][k+3];
                if(overlap && intersects(id,other)) {result[2]=id;result[3]=other;result[9]=checked;return reject(10);}
            }
        }
        timings[1]=milliseconds(start);start=Clock::now();
        if(std::memcmp(f,graph.facets.data(),3*nf*sizeof(std::int64_t))) return reject(11);
        if(!graph.valid_fans(nv)) return reject(12);
        timings[2]=milliseconds(start);start=Clock::now();
        // 完整操作和最终数组都通过才提交；旧编辑缓存失效，拒绝分支保持父状态原样。
        verified.graph=std::move(graph);verified.boxes=std::move(boxes);verified.editable.reset();
        result[0]=1;result[1]=1;result[2]=nv;result[3]=nf;result[4]=1;result[6]=1;result[8]=count;result[9]=checked;
        timings[3]=milliseconds(start);return 0;
    } catch(...) {return 2;}
}
