// 将各区域提出的准确边界补点同步到相邻三角形，不移动原边界端点。
void conform_quality_boundary_splits(
    Mesh& M, vector<index_t>& remove_f,
    const std::map<std::pair<index_t,index_t>,vector<index_t>>& requests
) {
    if(requests.empty()) return;
    remove_f.resize(M.facets.nb(),0);
    std::map<std::pair<index_t,index_t>,std::set<index_t>> incident;
    auto index_face=[&](index_t f) {
        for(index_t k=0;k<3;++k) {
            incident[std::minmax(M.facets.vertex(f,k),M.facets.vertex(f,(k+1)%3))].insert(f);
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
        auto found=incident.find(request.first);
        if(found==incident.end()) continue;
        const std::set<index_t> faces=found->second;
        for(index_t f:faces) {
            if(remove_f[f]) continue;
            index_t k=0;
            while(k<3 && std::pair<index_t,index_t>(std::minmax(M.facets.vertex(f,k),M.facets.vertex(f,(k+1)%3)))!=request.first) ++k;
            if(k==3) continue;
            vector<index_t> chain;
            const bool forward=M.facets.vertex(f,k)==a;
            chain.push_back(M.facets.vertex(f,k));
            if(forward) chain.insert(chain.end(),points.begin(),points.end());
            else chain.insert(chain.end(),points.rbegin(),points.rend());
            chain.push_back(M.facets.vertex(f,(k+1)%3));
            index_t opposite=M.facets.vertex(f,(k+2)%3);
            remove_f[f]=1;
            // 同一原边的补点排序后同时提交，两侧使用相同顶点编号和方向相反的边链。
            for(index_t i=0;i+1<chain.size();++i) {
                index_t child=M.facets.create_triangle(chain[i],chain[i+1],opposite);
                M.facets.attributes().copy_item(child,f);
                remove_f.push_back(0);index_face(child);
            }
        }
    }
}

struct NativeQualityScore {
    index_t bad=0,zero=0;
    long double area=0,total_area=0;
    bool finite=true;
};

// 整体比较绝对差面数量和面积，防止区域改善被相邻面的补点代价抵消。
NativeQualityScore native_quality_score(const Mesh& M,const vector<index_t>& cells) {
    NativeQualityScore result;
    for(index_t i=0;i<cells.size();i+=3) {
        const vec3 p[3]={M.vertices.point(cells[i]),M.vertices.point(cells[i+1]),M.vertices.point(cells[i+2])};
        double area=0.5*length(cross(p[1]-p[0],p[2]-p[0]));
        if(!std::isfinite(area)) {result.finite=false;break;}
        if(area==0.0) {++result.zero;continue;}
        result.total_area+=area;
        double angle=180.0;
        for(index_t k=0;k<3;++k) {
            vec3 x=p[(k+1)%3]-p[k],y=p[(k+2)%3]-p[k];
            angle=std::min(angle,std::atan2(length(cross(x,y)),dot(x,y))*180.0/3.14159265358979323846);
        }
        if(angle<10.0) {++result.bad;result.area+=area;}
    }
    return result;
}
