// 将同一原边两侧各自生成的点合并为一条完整边链，覆盖已经细分过的子边。
void conform_quality_boundary_splits(
    Mesh& M, vector<index_t>& remove_f,
    const std::map<std::pair<index_t,index_t>,vector<index_t>>& requests
) {
    if(requests.empty()) return;
    remove_f.resize(M.facets.nb(),0);
    std::map<std::pair<index_t,index_t>,std::set<index_t>> incident;
    std::map<index_t,std::set<index_t>> links;
    auto index_face=[&](index_t f) {
        for(index_t k=0;k<3;++k) {
            index_t a=M.facets.vertex(f,k),b=M.facets.vertex(f,(k+1)%3);
            incident[std::minmax(a,b)].insert(f);links[a].insert(b);links[b].insert(a);
        }
    };
    for(index_t f:M.facets) if(!remove_f[f]) index_face(f);
    for(const auto& request:requests) {
        index_t a=request.first.first,b=request.first.second;
        vector<index_t> points=request.second;
        const vec3 delta=M.vertices.point(b)-M.vertices.point(a);
        coord_index_t axis=0;
        for(coord_index_t k=1;k<3;++k) if(std::abs(delta[k])>std::abs(delta[axis])) axis=k;
        if(delta[axis]==0.0) continue;
        std::sort(points.begin(),points.end(),[&](index_t x,index_t y) {
            return (M.vertices.point(x)[axis]-M.vertices.point(a)[axis])/delta[axis] <
                   (M.vertices.point(y)[axis]-M.vertices.point(a)[axis])/delta[axis];
        });
        points.erase(std::unique(points.begin(),points.end()),points.end());
        vector<index_t> full_chain;full_chain.push_back(a);
        full_chain.insert(full_chain.end(),points.begin(),points.end());full_chain.push_back(b);
        std::map<index_t,index_t> rank;
        for(index_t i=0;i<full_chain.size();++i) rank[full_chain[i]]=i;
        std::set<std::pair<index_t,index_t>> affected;
        for(index_t v:full_chain) for(index_t q:links[v]) {
            auto found=rank.find(q);
            if(found!=rank.end() && std::max(rank[v],found->second)>std::min(rank[v],found->second)+1) {
                affected.insert(std::minmax(v,q));
            }
        }
        // 原边和已生成子边都检查；两侧已各自细分时也补齐对方新增点。
        for(auto edge:affected) {
            const std::set<index_t> faces=incident[edge];
            index_t begin=std::min(rank[edge.first],rank[edge.second]);
            index_t end=std::max(rank[edge.first],rank[edge.second]);
            for(index_t f:faces) {
                if(remove_f[f]) continue;
                index_t k=0;
                while(k<3 && std::pair<index_t,index_t>(std::minmax(M.facets.vertex(f,k),M.facets.vertex(f,(k+1)%3)))!=edge) ++k;
                if(k==3) continue;
                vector<index_t> chain;
                for(index_t i=begin;i<=end;++i) chain.push_back(full_chain[i]);
                if(M.facets.vertex(f,k)!=chain.front()) std::reverse(chain.begin(),chain.end());
                index_t opposite=M.facets.vertex(f,(k+2)%3);remove_f[f]=1;
                for(index_t i=0;i+1<chain.size();++i) {
                    index_t child=M.facets.create_triangle(chain[i],chain[i+1],opposite);
                    M.facets.attributes().copy_item(child,f);remove_f.push_back(0);index_face(child);
                }
            }
        }
    }
}
