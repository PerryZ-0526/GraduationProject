// 只收缩已经存在于输出面的零长度边，所有保留顶点的双精度坐标均不移动。
void contract_collapsed_float_edges(Mesh& M) {
    std::set<std::pair<index_t,index_t>> candidates;
    for(index_t f:M.facets) {
        if(M.facets.nb_vertices(f)!=3) return;
        for(index_t k=0; k<3; ++k) {
            index_t a=M.facets.vertex(f,k),b=M.facets.vertex(f,(k+1)%3);
            if(a==b) continue;
            const vec3& p=M.vertices.point(a);
            const vec3& q=M.vertices.point(b);
            // 非有限坐标不能被当作合法的零长度边。
            if(std::isfinite(p.x) && std::isfinite(p.y) && std::isfinite(p.z) &&
               p.x==q.x && p.y==q.y && p.z==q.z) candidates.insert(std::minmax(a,b));
        }
    }
    if(candidates.empty()) return;
    vector<index_t> redirect(M.vertices.nb());
    for(index_t v=0; v<M.vertices.nb(); ++v) redirect[v]=v;
    std::set<index_t> used;
    index_t accepted=0;
    for(auto edge:candidates) {
        index_t a=edge.first,b=edge.second;
        std::set<index_t> ring_a,ring_b,opposite;
        index_t incident=0;
        for(index_t f:M.facets) {
            bool has_a=false,has_b=false;
            for(index_t k=0; k<3; ++k) {
                has_a=has_a || M.facets.vertex(f,k)==a;
                has_b=has_b || M.facets.vertex(f,k)==b;
            }
            if(has_a) for(index_t k=0; k<3; ++k) ring_a.insert(M.facets.vertex(f,k));
            if(has_b) for(index_t k=0; k<3; ++k) ring_b.insert(M.facets.vertex(f,k));
            if(has_a && has_b) {
                ++incident;
                for(index_t k=0; k<3; ++k) {
                    index_t v=M.facets.vertex(f,k);
                    if(v!=a && v!=b) opposite.insert(v);
                }
            }
        }
        ring_a.erase(a);ring_a.erase(b);ring_b.erase(a);ring_b.erase(b);
        std::set<index_t> common;
        std::set_intersection(ring_a.begin(),ring_a.end(),ring_b.begin(),ring_b.end(),
                              std::inserter(common,common.begin()));
        // 闭合流形边须有两张邻面，顶点链接交集必须恰为两张邻面的对顶点。
        if(incident!=2 || opposite.size()!=2 || common!=opposite) continue;
        std::set<index_t> neighborhood=ring_a;
        neighborhood.insert(ring_b.begin(),ring_b.end());neighborhood.insert(a);neighborhood.insert(b);
        bool conflict=false;
        for(index_t v:neighborhood) conflict=conflict || used.count(v)!=0;
        if(conflict) continue;
        // 同轮收缩的一环互不相交，防止单项合法但组合改变局部拓扑。
        used.insert(neighborhood.begin(),neighborhood.end());
        redirect[b]=a;++accepted;
    }
    if(accepted==0) return;
    vector<index_t> remove(M.facets.nb(),0);
    for(index_t f:M.facets) {
        index_t vertices[3];
        for(index_t k=0; k<3; ++k) {
            vertices[k]=redirect[M.facets.vertex(f,k)];
            M.facets.set_vertex(f,k,vertices[k]);
        }
        // 删除的面已经是同坐标顶点退化的零面积映像，不删除其他小面积面。
        remove[f]=(vertices[0]==vertices[1] || vertices[1]==vertices[2] || vertices[2]==vertices[0]);
    }
    M.facets.delete_elements(remove);
    M.facets.connect();
    Logger::out("FloatEdge") << "contracted_zero_length_edges=" << accepted << std::endl;
}
