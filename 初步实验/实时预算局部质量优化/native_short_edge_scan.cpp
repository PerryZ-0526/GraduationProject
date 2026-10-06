// 单次遍历生成全域面包围盒和保守短边候选，最终阈值仍由原NumPy范数筛选。
#include <algorithm>
#include <cmath>
#include <cstdint>

extern "C" int64_t scan_short_edges(const double* v,int64_t nv,const int64_t* f,int64_t nf,
                                   double tolerance,double* low,double* high,int64_t* edges) {
    if(!(tolerance>0) || !std::isfinite(tolerance)) return -1;
    int64_t count=0;
    for(int64_t i=0;i<nf;++i) {
        const int64_t* tri=f+3*i;
        for(int k=0;k<3;++k) {
            if(tri[k]<0 || tri[k]>=nv) return -2;
            for(int d=0;d<3;++d) if(!std::isfinite(v[3*tri[k]+d])) return -3;
        }
        for(int d=0;d<3;++d) {
            low[3*i+d]=std::min(std::min(v[3*tri[0]+d],v[3*tri[1]+d]),v[3*tri[2]+d]);
            high[3*i+d]=std::max(std::max(v[3*tri[0]+d],v[3*tri[1]+d]),v[3*tri[2]+d]);
        }
        for(int k=0;k<3;++k) {
            int64_t a=tri[k],b=tri[(k+1)%3];
            // 固定毫米容差的两倍立方体仅作宽筛，不代替准确位移界或碰撞检查。
            bool near=true;
            for(int d=0;d<3;++d) near=near && std::abs(v[3*a+d]-v[3*b+d])<=2*tolerance;
            if(near) {edges[2*count]=std::min(a,b);edges[2*count+1]=std::max(a,b);++count;}
        }
    }
    return count;
}
