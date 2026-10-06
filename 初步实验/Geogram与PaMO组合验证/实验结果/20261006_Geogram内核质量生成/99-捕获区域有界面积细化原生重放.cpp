#include <geogram/basic/common.h>
#include <geogram/delaunay/delaunay_triangle.h>
#include <array>
#include <vector>
#include <fstream>
#include <iostream>
#include <iomanip>
#include <cmath>
#include <algorithm>
#include <cstdlib>
#include <cstdio>
#include <string>

using Point=std::array<double,3>;
Point subtract(Point a,Point b) {for(int d=0;d<3;++d) a[d]-=b[d];return a;}
Point cross3(Point a,Point b) {return {a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]};}
double dot3(Point a,Point b) {double s=0;for(int d=0;d<3;++d)s+=a[d]*b[d];return s;}
double norm3(Point a) {return std::sqrt(dot3(a,a));}

// 原生区域重放仅用于确定有界细化是否可行，不作完整布尔或速度交付。
int main(int argc,char** argv) {
    if(argc<5) return 2;
    std::ifstream stream(argv[1]);int n,nt,ns,u,v;stream>>n>>nt>>ns>>u>>v;
    std::vector<double> xy(2*n);std::vector<Point> xyz(n);
    std::vector<int> cells(3*nt),segments(2*ns),markers(ns);
    for(double& x:xy) stream>>x;
    for(Point& p:xyz) for(double& x:p) stream>>x;
    for(int& x:cells) stream>>x;
    for(int& x:segments) stream>>x;
    for(int i=0;i<ns;++i) markers[i]=i+1;
    if(!stream) return 3;
    double offset[2]={0,0},scale=1.0;
    if(std::string(argv[4])=="normalize") {
        double lower[2]={xy[0],xy[1]},upper[2]={xy[0],xy[1]};
        for(int i=0;i<n;++i) for(int d=0;d<2;++d) {lower[d]=std::min(lower[d],xy[2*i+d]);upper[d]=std::max(upper[d],xy[2*i+d]);}
        for(int d=0;d<2;++d) offset[d]=0.5*(lower[d]+upper[d]);
        scale=std::max(upper[0]-lower[0],upper[1]-lower[1]);
        for(int i=0;i<n;++i) for(int d=0;d<2;++d) xy[2*i+d]=(xy[2*i+d]-offset[d])/scale;
    }
    int k=3-u-v,seed=0;double largest=0;
    for(int i=0;i<nt;++i) {
        double area=norm3(cross3(subtract(xyz[cells[3*i+1]],xyz[cells[3*i]]),subtract(xyz[cells[3*i+2]],xyz[cells[3*i]])));
        if(area>largest) {largest=area;seed=i;}
    }
    Point origin=xyz[cells[3*seed]],normal=cross3(subtract(xyz[cells[3*seed+1]],origin),subtract(xyz[cells[3*seed+2]],origin));
    if(normal[k]==0 || scale==0) return 4;
    auto lift=[&](int id,const double* points) {
        if(id<n) return xyz[id];
        Point p=origin;p[u]=points[2*id]*scale+offset[0];p[v]=points[2*id+1]*scale+offset[1];
        p[k]=origin[k]-(normal[u]*(p[u]-origin[u])+normal[v]*(p[v]-origin[v]))/normal[k];return p;
    };
    struct Score {int bad=0,zero=0;double area=0,min_angle=180;std::vector<bool> mask;};
    auto score=[&](int count,const int* triangles,const double* points) {
        Score s;s.mask.resize(count);
        for(int i=0;i<count;++i) {
            Point p[3]={lift(triangles[3*i],points),lift(triangles[3*i+1],points),lift(triangles[3*i+2],points)};
            double area=0.5*norm3(cross3(subtract(p[1],p[0]),subtract(p[2],p[0]))),angle=180;
            if(area<=0 || !std::isfinite(area)) {++s.zero;continue;}
            for(int d=0;d<3;++d) {Point a=subtract(p[(d+1)%3],p[d]),b=subtract(p[(d+2)%3],p[d]);angle=std::min(angle,std::atan2(norm3(cross3(a,b)),dot3(a,b))*180.0/3.14159265358979323846);}
            s.min_angle=std::min(s.min_angle,angle);s.mask[i]=angle<10;
            if(s.mask[i]) {++s.bad;s.area+=area;}
        }
        return s;
    };
    auto print=[&](const char* stage,Score s,int points,int triangles) {
        std::cout<<std::setprecision(17)<<"REPLAY_STAGE {\"stage\":\""<<stage<<"\",\"points\":"<<points<<",\"triangles\":"<<triangles<<",\"bad\":"<<s.bad<<",\"zero\":"<<s.zero<<",\"bad_area\":"<<s.area<<",\"min_angle\":"<<s.min_angle<<"}"<<std::endl;
    };
    auto release=[](triangulateio& t) {
        free(t.pointlist);free(t.pointattributelist);free(t.pointmarkerlist);free(t.trianglelist);free(t.triangleattributelist);
        free(t.trianglearealist);free(t.neighborlist);free(t.segmentlist);free(t.segmentmarkerlist);free(t.edgelist);free(t.edgemarkerlist);free(t.normlist);
    };
    triangulateio input{},output{};input.pointlist=xy.data();input.numberofpoints=n;
    input.trianglelist=cells.data();input.numberoftriangles=nt;input.numberofcorners=3;
    input.segmentlist=segments.data();input.numberofsegments=ns;input.segmentmarkerlist=markers.data();
    Score before=score(nt,cells.data(),xy.data());print("input",before,n,nt);
    std::string options=argv[2];std::vector<char> switches(options.begin(),options.end());switches.push_back(0);
    ::triangulate(switches.data(),&input,&output,nullptr);
    Score after=score(output.numberoftriangles,output.trianglelist,output.pointlist);print("quality",after,output.numberofpoints,output.numberoftriangles);
    // 只对质量候选中仍然过大的差面再细化一次，全部点数共享同一总预算。
    int total_budget=std::atoi(argv[3]),remaining=total_budget-(output.numberofpoints-n);
    if(after.bad>0 && after.area>before.area && remaining>0) {
        std::vector<double> limits(output.numberoftriangles,-1.0);
        double projected_ratio=std::abs(normal[k])/norm3(normal);
        double limit=before.area/(2.0*after.bad)*projected_ratio/(scale*scale);
        for(int i=0;i<output.numberoftriangles;++i) if(after.mask[i]) limits[i]=limit;
        triangulateio refine{},next{};
        refine.pointlist=output.pointlist;refine.numberofpoints=output.numberofpoints;
        refine.trianglelist=output.trianglelist;refine.numberoftriangles=output.numberoftriangles;refine.numberofcorners=3;refine.trianglearealist=limits.data();
        refine.segmentlist=output.segmentlist;refine.numberofsegments=output.numberofsegments;refine.segmentmarkerlist=output.segmentmarkerlist;
        char area_options[64];std::snprintf(area_options,sizeof(area_options),"rpza%sS%dQ",options.find("YY")!=std::string::npos ? "YY" : "",remaining);
        ::triangulate(area_options,&refine,&next,nullptr);
        release(output);output=next;after=score(output.numberoftriangles,output.trianglelist,output.pointlist);
        print("targeted_area",after,output.numberofpoints,output.numberoftriangles);
    }
    release(output);return 0;
}
