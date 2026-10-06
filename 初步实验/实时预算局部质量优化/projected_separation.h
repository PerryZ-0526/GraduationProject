// 将60号准确投影排除封装成可延后建立的查询数据；不改变零值与接触判据。
#pragma once
struct ProjectedSeparation {
    using Triangle=std::array<PredicateKernel::Point_2,3>;
    const std::int64_t* facets;
    std::vector<std::array<Triangle,3>> projections;
    std::vector<std::array<CGAL::Orientation,3>> directions;
    std::vector<int> dominant;
    PredicateKernel::Orientation_2 orientation;
    ProjectedSeparation(const double* v,const std::int64_t* f,std::uint64_t nf)
        :facets(f),projections(nf),directions(nf),dominant(nf,2),orientation(PredicateKernel().orientation_2_object()) {
        for(std::uint64_t i=0;i<nf;++i) {
            const auto* tri=f+3*i;double e[3],g[3],normal[3];
            for(int k=0;k<3;++k) {e[k]=v[3*tri[1]+k]-v[3*tri[0]+k];g[k]=v[3*tri[2]+k]-v[3*tri[0]+k];}
            // 计算法向仅安排查询次序；实际分离仍由准确二维方向谓词裁决。
            for(int k=0;k<3;++k) normal[k]=std::abs(e[(k+1)%3]*g[(k+2)%3]-e[(k+2)%3]*g[(k+1)%3]);
            dominant[i]=std::max_element(normal,normal+3)-normal;
            for(int axis=0;axis<3;++axis) {
                int x=(axis+1)%3,y=(axis+2)%3;auto& points=projections[i][axis];
                for(int j=0;j<3;++j) points[j]=PredicateKernel::Point_2(v[3*tri[j]+x],v[3*tri[j]+y]);
                directions[i][axis]=orientation(points[0],points[1],points[2]);
            }
        }
    }
    bool separated(std::uint64_t i,std::uint64_t j) const {
        const auto* a=facets+3*i;const auto* b=facets+3*j;
        for(int p=0;p<3;++p) for(int q=0;q<3;++q) if(a[p]==b[q]) return false;
        auto on_projection=[&](int axis) {
            const auto& p=projections[i][axis];const auto& q=projections[j][axis];
            auto outside=[&](const Triangle& triangle,const Triangle& other,CGAL::Orientation side) {
                if(side==CGAL::COLLINEAR) return false;
                for(int edge=0;edge<3;++edge) {
                    bool separated=true;
                    for(int k=0;k<3;++k) {
                        auto sign=orientation(triangle[edge],triangle[(edge+1)%3],other[k]);
                        if(sign==CGAL::COLLINEAR || sign==side) {separated=false;break;}
                    }
                    if(separated) return true;
                }
                return false;
            };
            return outside(p,q,directions[i][axis]) || outside(q,p,directions[j][axis]);
        };
        return on_projection(dominant[i]) || (dominant[i]!=dominant[j] && on_projection(dominant[j]));
    }
};
