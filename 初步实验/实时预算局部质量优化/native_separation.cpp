// 保留原精确分离与共同实体支撑规则；二进制浮点坐标转为共同尺度的整数。
#include <array>
#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstring>
#include <boost/multiprecision/cpp_int.hpp>

using Integer = boost::multiprecision::cpp_int;
using Point = std::array<Integer, 3>;

// Windows明确导出同一精确核，Linux沿用原C接口，算术和判据不变。
#ifdef _WIN32
#define EXACT_API extern "C" __declspec(dllexport)
#else
#define EXACT_API extern "C"
#endif

static Point subtract(const Point& a, const Point& b) {
    return {a[0]-b[0], a[1]-b[1], a[2]-b[2]};
}
static Point cross(const Point& a, const Point& b) {
    return {a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]};
}
static Integer dot(const Point& a, const Point& b) {
    return a[0]*b[0]+a[1]*b[1]+a[2]*b[2];
}
EXACT_API double separation_clock() {
    return std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count();
}
EXACT_API int separate_triangles(const double* coordinates, const std::int64_t* ids, double deadline) {
    // 先约去尾部二次幂，避免正常坐标也使用次正规数的巨大公共分母。
    std::array<std::uint64_t, 18> mantissa{};
    std::array<int, 18> exponent{};
    std::array<bool, 18> negative{};
    int denominator_power = 0;
    for (int k=0; k<18; ++k) {
        std::uint64_t bits;
        std::memcpy(&bits, coordinates+k, sizeof(bits));
        int encoded = (bits >> 52) & 2047;
        if (encoded == 2047) return -2;
        negative[k] = (bits >> 63) != 0;
        mantissa[k] = bits & ((std::uint64_t(1)<<52)-1);
        exponent[k] = encoded ? encoded-1023-52 : -1074;
        if (encoded) mantissa[k] |= std::uint64_t(1)<<52;
        if (!mantissa[k]) { exponent[k]=0; continue; }
        while (!(mantissa[k]&1)) { mantissa[k] >>= 1; ++exponent[k]; }
        denominator_power = std::max(denominator_power, -exponent[k]);
    }
    std::array<Point, 6> points;
    for (int k=0; k<18; ++k) {
        Integer value = mantissa[k];
        value <<= exponent[k]+denominator_power;
        points[k/3][k%3] = negative[k] ? -value : value;
    }
    std::array<bool, 6> shared{};
    int shared_count=0;
    for (int i=0; i<3; ++i) for (int j=3; j<6; ++j) {
        if (ids[i]==ids[j]) { shared[i]=true; shared[j]=true; }
    }
    for (int i=0; i<3; ++i) shared_count += shared[i];
    if (shared_count==3) return 0;
    std::array<Point, 3> aedge, bedge;
    for (int k=0; k<3; ++k) {
        aedge[k]=subtract(points[(k+1)%3],points[k]);
        bedge[k]=subtract(points[3+(k+1)%3],points[3+k]);
    }
    Point an=cross(aedge[0],aedge[1]), bn=cross(bedge[0],bedge[1]);
    std::array<Point, 17> axes;
    axes[0]=an; axes[1]=bn; int index=2;
    for (const auto& x:aedge) for (const auto& y:bedge) axes[index++]=cross(x,y);
    for (const auto& x:aedge) axes[index++]=cross(an,x);
    for (const auto& x:bedge) axes[index++]=cross(bn,x);
    for (const auto& axis:axes) {
        // 与Python相同，每条轴开始前检查实际截止时钟，不隐藏不可抢占操作。
        if (separation_clock()>=deadline) return -1;
        if (axis[0]==0 && axis[1]==0 && axis[2]==0) continue;
        std::array<Integer, 6> values;
        for (int k=0; k<6; ++k) values[k]=dot(points[k],axis);
        for (int direction=0; direction<2; ++direction) {
            int first=direction*3, second=(1-direction)*3;
            Integer high=values[first], low=values[second];
            for (int k=1; k<3; ++k) {
                high=std::max(high,values[first+k]); low=std::min(low,values[second+k]);
            }
            if (high<low) return 1;
            if (high==low && shared_count) {
                bool support_shared=true, other_shared=true;
                for (int k=0; k<3; ++k) {
                    if (values[first+k]==high && !shared[first+k]) support_shared=false;
                    if (values[second+k]==low && !shared[second+k]) other_shared=false;
                }
                if (support_shared || other_shared) return 1;
            }
        }
    }
    return 0;
}
