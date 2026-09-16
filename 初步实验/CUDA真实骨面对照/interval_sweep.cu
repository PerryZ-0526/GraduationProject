// 向外舍入区间包围同一水平扫掠公式；输入为有限双精度实数，不开启快速数学。
struct I { double l, h; };
__device__ I pt(double x) { return {x,x}; }
__device__ I add(I a,I b) { return {__dadd_rd(a.l,b.l),__dadd_ru(a.h,b.h)}; }
__device__ I sub(I a,I b) { return {__dsub_rd(a.l,b.h),__dsub_ru(a.h,b.l)}; }
__device__ I mul(I a,I b) {
    return {fmin(fmin(__dmul_rd(a.l,b.l),__dmul_rd(a.l,b.h)),fmin(__dmul_rd(a.h,b.l),__dmul_rd(a.h,b.h))),
            fmax(fmax(__dmul_ru(a.l,b.l),__dmul_ru(a.l,b.h)),fmax(__dmul_ru(a.h,b.l),__dmul_ru(a.h,b.h)))};
}
__device__ I sq(I a) {
    double low=a.l<=0 && a.h>=0?0:fmin(__dmul_rd(a.l,a.l),__dmul_rd(a.h,a.h));
    return {low,fmax(__dmul_ru(a.l,a.l),__dmul_ru(a.h,a.h))};
}
__device__ I divide_positive(I a,I b) { return mul(a,{__ddiv_rd(1.,b.h),__ddiv_ru(1.,b.l)}); }
__device__ I minimum(I a,I b) { return {fmin(a.l,b.l),fmin(a.h,b.h)}; }
extern "C" __global__ void sweep(const double* xy,const double* base,const double* tools,
    int count,double* out,int n) {
    int i=blockIdx.x*blockDim.x+threadIdx.x;
    if(i>=n) return;
    I value=pt(base[i]);
    for(int j=0;j<count;j++) {
        const double* t=tools+6*j;
        I dx=sub(pt(t[2]),pt(t[0])),dy=sub(pt(t[3]),pt(t[1]));
        I x=sub(pt(xy[2*i]),pt(t[0])),y=sub(pt(xy[2*i+1]),pt(t[1]));
        I u=pt(0.);
        if(t[0]!=t[2] || t[1]!=t[3]) {
            I len=add(sq(dx),sq(dy));
            if(!(len.l>0)) { out[2*i]=out[2*i+1]=nan(""); return; }
            u=divide_positive(add(mul(x,dx),mul(y,dy)),len);
            u={fmin(1.,fmax(0.,u.l)),fmin(1.,fmax(0.,u.h))};
        }
        I d2=add(sq(sub(x,mul(u,dx))),sq(sub(y,mul(u,dy))));
        I r2=sq(pt(t[4]));
        if(d2.l>r2.h) continue;
        I rad=sub(r2,d2);
        rad={fmax(0.,rad.l),fmax(0.,rad.h)};
        I lower=sub(pt(t[5]),{__dsqrt_rd(rad.l),__dsqrt_ru(rad.h)});
        I inside=minimum(value,lower);
        // 足迹分支不确定时，取内外两种结果的区间包络，禁止猜测分支。
        value=d2.h<=r2.l?inside:I{fmin(value.l,inside.l),fmax(value.h,inside.h)};
    }
    out[2*i]=value.l;
    out[2*i+1]=value.h;
}
