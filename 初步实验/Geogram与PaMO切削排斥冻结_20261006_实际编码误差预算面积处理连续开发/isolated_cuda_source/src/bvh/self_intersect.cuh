#pragma once
namespace cusimp_free {
    class CUSimp_Free;
    // 从实际设备表示取回完整坐标和面，不复用原近似报警集合。
    bool exact_native_self_intersect(CUSimp_Free*, unsigned int, unsigned int);
}
namespace selfx {
    inline bool self_intersect(cusimp_free::CUSimp_Free* sp, unsigned int nv, unsigned int nf, float) {
        return cusimp_free::exact_native_self_intersect(sp,nv,nf);
    }
}
