// 与既有OpenCL及CPU参考相同的水平球心扫掠下包络，所有长度为毫米。
extern "C" __global__ void sweep(const double* xy, const double* base,
    const double* tools, int count, double* out, int n) {
    int i=blockIdx.x*blockDim.x+threadIdx.x;
    if(i>=n) return;
    double value=base[i], x=xy[2*i], y=xy[2*i+1];
    for(int j=0;j<count;j++) {
        const double* t=tools+6*j;
        double dx=t[2]-t[0], dy=t[3]-t[1], length2=dx*dx+dy*dy;
        double u=length2==0?0:fmin(1.,fmax(0.,((x-t[0])*dx+(y-t[1])*dy)/length2));
        double rx=x-t[0]-u*dx, ry=y-t[1]-u*dy, d2=rx*rx+ry*ry;
        if(d2<=t[4]*t[4]) value=fmin(value,t[5]-sqrt(fmax(0.,t[4]*t[4]-d2)));
    }
    out[i]=value;
}
