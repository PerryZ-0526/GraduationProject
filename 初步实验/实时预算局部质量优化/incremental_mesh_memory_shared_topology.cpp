// 复用已通过精确认证的数组半边；原认证和事务实现保持逐字节包含。
#include "incremental_mesh_memory_array.cpp"

EXACT_MEMORY_API int bind_quality_topology(const void* state,const double* v,std::uint64_t nv,
    const std::int64_t* f,std::uint64_t nf) {
    if(!state || !v || !f) return 1;
    const auto& parent=*static_cast<const ArrayVerifiedState*>(state);
    // 仅同坐标、同有向面数组允许复用；摘要相等或外部成功标志不能替代实际字节核对。
    if(parent.coordinates.size()!=3*nv || parent.graph.facets.size()!=3*nf || !parent.graph.closed_manifold) return 2;
    return std::memcmp(v,parent.coordinates.data(),3*nv*sizeof(double))==0 &&
        std::memcmp(f,parent.graph.facets.data(),3*nf*sizeof(std::int64_t))==0 ? 0 : 2;
}

EXACT_MEMORY_API int quality_edge_owners(const void* state,std::int64_t a,std::int64_t b,std::int64_t* owners) {
    if(!state || !owners) return -1;
    const auto& parent=*static_cast<const ArrayVerifiedState*>(state);
    if(a<0 || b<0 || a>=std::int64_t(parent.coordinates.size()/3) || b>=std::int64_t(parent.coordinates.size()/3)) return -1;
    if(a==b) return 0;
    auto edge=parent.graph.find(a,b);
    if(edge==ArrayTopology::absent) return 0;
    // 查询完整父图，活动域外已有对角线同样阻止局部翻边，不裁去外部障碍。
    auto opposite=parent.graph.opposite_edges[edge];
    if(opposite==ArrayTopology::absent) return -1;
    owners[0]=edge/3;owners[1]=opposite/3;
    return 2;
}
