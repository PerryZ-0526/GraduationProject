// 六个固定对角方向只提供保守分离证据；重叠仍需原精确面相交谓词。
#pragma once
#include <array>
#include <cmath>
#include <cstring>
#include <cstdint>
#include <limits>
#include <vector>

struct DirectionalBounds {
    using Bounds=std::array<double,12>;
    std::vector<Bounds> faces;
    static bool subnormal(double value) {
        std::uint64_t bits;std::memcpy(&bits,&value,sizeof(bits));bits&=0x7fffffffffffffffULL;
        return bits && (bits>>52)==0;
    }
    static Bounds point(const double* p) {
        Bounds result;const double infinity=std::numeric_limits<double>::infinity();
        // 非正规数输入不在方向筛选中计算，避免DAZ/FTZ改变其准确几何意义。
        if(subnormal(p[0]) || subnormal(p[1]) || subnormal(p[2])) {
            for(int k=0;k<6;++k) {result[k]=-infinity;result[k+6]=infinity;}
            return result;
        }
        const double values[6]={p[0]+p[1],p[0]-p[1],p[0]+p[2],p[0]-p[2],p[1]+p[2],p[1]-p[2]};
        for(int k=0;k<6;++k) {
            const double value=values[k];
            if(value==0 || subnormal(value)) {
                // 正规输入相消的非正规结果即使被清零，也包含在最小正规数范围内。
                result[k]=-std::numeric_limits<double>::min();result[k+6]=std::numeric_limits<double>::min();
            } else {
                // IEEE加减任意舍入模式的相邻可表示数包住准确和；溢出端保持无穷界。
                result[k]=std::nextafter(value,-infinity);result[k+6]=std::nextafter(value,infinity);
            }
        }
        return result;
    }
    DirectionalBounds(const double* v,std::uint64_t nv,const std::int64_t* f,std::uint64_t nf) {
        std::vector<Bounds> points;points.reserve(nv);
        for(std::uint64_t i=0;i<nv;++i) points.push_back(point(v+3*i));
        faces.reserve(nf);
        for(std::uint64_t i=0;i<nf;++i) {
            auto bounds=points[f[3*i]];
            for(int j=1;j<3;++j) for(int k=0;k<6;++k) {
                const auto& p=points[f[3*i+j]];
                bounds[k]=std::min(bounds[k],p[k]);bounds[k+6]=std::max(bounds[k+6],p[k+6]);
            }
            faces.push_back(bounds);
        }
    }
    bool separated(std::uint64_t a,std::uint64_t b) const {
        const auto& left=faces[a];const auto& right=faces[b];
        for(int k=0;k<6;++k) if(left[k+6]<right[k] || right[k+6]<left[k]) return true;
        return false;
    }
};
