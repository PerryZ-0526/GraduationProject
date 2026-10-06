// 此方法在Geogram区域三角化阶段执行，保持已有边界，直接生成返回网格。
bool CoplanarFacets::quality_triangulate(
    vector<index_t>& triangles, vector<ExactPoint>& new_points
) {
#ifndef GEOGRAM_WITH_TRIANGLE
    return false;
#else
    struct Score { index_t bad=0; long double area=0; bool valid=true; };
    auto score = [](const vector<vec3>& points, const vector<int>& cells) {
        Score result;
        for(index_t i=0; i<cells.size(); i+=3) {
            const vec3& a=points[cells[i]];
            const vec3& b=points[cells[i+1]];
            const vec3& c=points[cells[i+2]];
            double area=0.5*length(cross(b-a,c-a));
            if(!std::isfinite(area) || area<=0.0) {result.valid=false; break;}
            double angle=180.0;
            const vec3 corners[3]={a,b,c};
            for(int k=0; k<3; ++k) {
                vec3 x=corners[(k+1)%3]-corners[k];
                vec3 y=corners[(k+2)%3]-corners[k];
                angle=std::min(angle,std::atan2(length(cross(x,y)),dot(x,y))*180.0/3.14159265358979323846);
            }
            if(angle<10.0) {++result.bad; result.area+=area;}
        }
        return result;
    };

    // 只处理确有差面的区域，零差面不调用额外生成器。
    std::map<index_t,int> local;
    vector<index_t> ids;
    vector<double> xy;
    vector<vec3> xyz;
    vector<int> cells;
    for(index_t t=0; t<CDT.nT(); ++t) {
        for(index_t k=0; k<3; ++k) {
            index_t v=CDT.Tv(t,k);
            auto found=local.find(v);
            if(found==local.end()) {
                index_t id=CDT.vertex_id(v);
                if(id==NO_INDEX) return false;
                int index=int(ids.size());
                local[v]=index;
                ids.push_back(id);
                const auto& p=CDT.point(v);
                xy.push_back(p.x.estimate()/p.w.estimate());
                xy.push_back(p.y.estimate()/p.w.estimate());
                xyz.push_back(mesh_.vertices.point(id));
                cells.push_back(index);
            } else {
                cells.push_back(found->second);
            }
        }
    }
    Score before=score(xyz,cells);
    if(!before.valid || before.bad==0 || cells.empty()) return false;

    // 原版准确CDT确定区域和孔洞；Triangle只细化这份已确定的内部三角集合。
    std::set<std::pair<int,int>> boundaries;
    for(index_t t=0; t<CDT.nT(); ++t) {
        for(index_t k=0; k<3; ++k) {
            if(CDT.Tedge_cnstr_first(t,k)!=NO_INDEX) {
                int a=local.at(CDT.Tv(t,(k+1)%3));
                int b=local.at(CDT.Tv(t,(k+2)%3));
                boundaries.insert(std::minmax(a,b));
            }
        }
    }
    vector<int> segments;
    for(auto edge:boundaries) {segments.push_back(edge.first); segments.push_back(edge.second);}
    double orientation=(xy[2*cells[1]]-xy[2*cells[0]])*(xy[2*cells[2]+1]-xy[2*cells[0]+1])-
        (xy[2*cells[1]+1]-xy[2*cells[0]+1])*(xy[2*cells[2]]-xy[2*cells[0]]);
    // 双精度投影已失去正面积的区域保留准确CDT，不送入浮点细化器。
    for(index_t i=0; i<cells.size(); i+=3) {
        int a=cells[i],b=cells[i+1],c=cells[i+2];
        double signed_area=(xy[2*b]-xy[2*a])*(xy[2*c+1]-xy[2*a+1])-
            (xy[2*b+1]-xy[2*a+1])*(xy[2*c]-xy[2*a]);
        if(!std::isfinite(signed_area) || signed_area==0.0) return false;
        if(signed_area<0.0) std::swap(cells[i+1],cells[i+2]);
    }
    triangulateio input{},output{};
    input.pointlist=xy.data(); input.numberofpoints=int(ids.size());
    input.trianglelist=cells.data(); input.numberoftriangles=int(cells.size()/3); input.numberofcorners=3;
    input.segmentlist=segments.data(); input.numberofsegments=int(segments.size()/2);
    // 保留已有约束段并禁止边界补点，新增内部点最多六十四个。
    char options[]="rpzq20YYS64Q";
    // Triangle初始化含共享全局常量，串行保护其调用；区域提取仍由Geogram并行执行。
    static std::mutex triangle_mutex;
    {
        std::lock_guard<std::mutex> guard(triangle_mutex);
        ::triangulate(options,&input,&output,nullptr);
    }
    auto release=[&]() {
        free(output.pointlist); free(output.pointattributelist); free(output.pointmarkerlist);
        free(output.trianglelist); free(output.triangleattributelist); free(output.trianglearealist);
        free(output.neighborlist); free(output.segmentlist); free(output.segmentmarkerlist);
        free(output.edgelist); free(output.edgemarkerlist); free(output.normlist);
    };
    bool valid=output.numberofpoints>=int(ids.size()) && output.numberofpoints<=int(ids.size())+64 &&
        output.numberofcorners==3 && output.numberoftriangles>0;
    for(index_t i=0; valid && i<xy.size(); ++i) valid=(output.pointlist[i]==xy[i]);
    std::set<std::pair<int,int>> returned_boundaries;
    for(int i=0; valid && i<output.numberofsegments; ++i) {
        int a=output.segmentlist[2*i],b=output.segmentlist[2*i+1];
        valid=(a>=0 && b>=0 && a<int(ids.size()) && b<int(ids.size()));
        returned_boundaries.insert(std::minmax(a,b));
    }
    valid=valid && returned_boundaries==boundaries;

    // 新内部点准确提升到原支撑平面，原边界顶点及坐标逐项保持。
    ExactPoint a=I_.exact_vertex(mesh_.facets.vertex(facets_[0],0));
    ExactPoint b=I_.exact_vertex(mesh_.facets.vertex(facets_[0],1));
    ExactPoint c=I_.exact_vertex(mesh_.facets.vertex(facets_[0],2));
    ExactPoint ab=b-a,ac=c-a;
    exact::vec3 normal(
        ab.y*ac.z-ab.z*ac.y, ab.z*ac.x-ab.x*ac.z, ab.x*ac.y-ab.y*ac.x
    );
    coord_index_t k=coord_index_t(3-u_-v_);
    vector<ExactPoint> proposed;
    for(int i=int(ids.size()); valid && i<output.numberofpoints; ++i) {
        double x=output.pointlist[2*i],y=output.pointlist[2*i+1];
        valid=std::isfinite(x) && std::isfinite(y);
        if(!valid) break;
        ExactPoint p;
        p.w=normal[k]*a.w;
        p[u_]=x*p.w; p[v_]=y*p.w;
        p[k]=normal.x*a.x+normal.y*a.y+normal.z*a.z-a.w*(normal[u_]*x+normal[v_]*y);
        Numeric::optimize_number_representation(p);
        vec3 approximate=PCK::approximate(p);
        valid=std::isfinite(approximate.x) && std::isfinite(approximate.y) && std::isfinite(approximate.z);
        proposed.push_back(p);
        xyz.push_back(approximate);
    }
    vector<int> refined;
    if(valid) {
        for(int i=0; i<3*output.numberoftriangles; ++i) {
            int v=output.trianglelist[i];
            if(v<0 || v>=output.numberofpoints) {valid=false; break;}
            refined.push_back(v);
        }
    }
    Score after;
    if(valid) after=score(xyz,refined);
    valid=valid && after.valid && after.bad<=before.bad && after.area<=before.area &&
        (after.bad<before.bad || after.area<before.area);
    if(valid) {
        index_t original_vertices=mesh_.vertices.nb();
        for(index_t i=0; i<refined.size(); i+=3) {
            if(orientation<0.0) std::swap(refined[i+1],refined[i+2]);
            for(index_t j=0; j<3; ++j) {
                index_t v=index_t(refined[i+j]);
                triangles.push_back(v<ids.size() ? ids[v] : original_vertices+v-ids.size());
            }
        }
        new_points.swap(proposed);
    }
    release();
    return valid;
#endif
}
