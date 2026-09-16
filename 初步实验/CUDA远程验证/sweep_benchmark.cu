// 受限水平球心扫掠的CPU/CUDA双精度对拍，不代表完整网格更新。
#include <cuda_runtime.h>
#include <omp.h>
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <vector>

void check(cudaError_t e) {
    if(e != cudaSuccess) { fprintf(stderr,"CUDA: %s\n",cudaGetErrorString(e)); exit(2); }
}
// 所有长度单位为mm；记录每段两个XY端点、球半径与固定球心高度。
struct Tool { double ax, ay, bx, by, r, z; };
__host__ __device__ double query(double x, double y, double base, const Tool* t, int count) {
    for(int j=0;j<count;++j) {
        double dx=t[j].bx-t[j].ax, dy=t[j].by-t[j].ay;
        double l=dx*dx+dy*dy;
        double u=l==0?0:fmin(1.,fmax(0.,((x-t[j].ax)*dx+(y-t[j].ay)*dy)/l));
        double rx=x-t[j].ax-u*dx, ry=y-t[j].ay-u*dy;
        double d=rx*rx+ry*ry;
        if(d<=t[j].r*t[j].r) base=fmin(base,t[j].z-sqrt(fmax(0.,t[j].r*t[j].r-d)));
    }
    return base;
}
__global__ void sweep(const double* xy,const double* base,const Tool* tools,int count,double* out,int n) {
    int i=blockIdx.x*blockDim.x+threadIdx.x;
    if(i<n) out[i]=query(xy[2*i],xy[2*i+1],base[i],tools,count);
}
using Clock=std::chrono::steady_clock;
double elapsed(Clock::time_point start) { return std::chrono::duration<double,std::milli>(Clock::now()-start).count(); }
int main() {
    omp_set_num_threads(4);
    // 已知真值：静止半径2球心z=1，中心=-1，球赤道点=1，外部保持原面。
    Tool simple{0,0,0,0,2,1};
    if(query(0,0,3,&simple,1)!=-1 || query(2,0,3,&simple,1)!=1 || query(3,0,3,&simple,1)!=3) return 3;
    Tool line{-1,0,1,0,2,1};
    if(query(0,0,3,&line,1)!=-1 || query(1,2,3,&line,1)!=1) return 3;
    printf("{\"analytic_cpu_checks\":5,\"cpu_threads\":4,\"warmup\":5,\"repeats\":20,\"cases\":[\n");
    bool first=true;
    for(int n: {1024,16384,131072}) for(int count: {16,138}) {
        std::vector<double> xy(2*n),base(n,3),cpu(n),gpu(n);
        std::vector<Tool> tools(count);
        // 确定性均匀网格及交错轨迹，不依赖随机数实现或库版本。
        for(int i=0;i<n;i++) { xy[2*i]=(i%512)/511.0*16-8; xy[2*i+1]=(i/512)/double(std::max(1,(n-1)/512))*16-8; }
        for(int j=0;j<count;j++) tools[j]={-4.,-4.+8.*j/count,4.,-4.+8.*j/count,2.,1.8};
        // 追加相切、球心下方、重复端点等显式输入到全部规模中。
        xy[0]=-4; xy[1]=-4; xy[2]=-4; xy[3]=-6;
        double *dx,*db,*out; Tool* dt;
        check(cudaMalloc(&dx,xy.size()*8)); check(cudaMalloc(&db,n*8));
        check(cudaMalloc(&out,n*8)); check(cudaMalloc(&dt,count*sizeof(Tool)));
        cudaEvent_t start,end; check(cudaEventCreate(&start));check(cudaEventCreate(&end));
        std::vector<double> ct,kt,et;
        for(int rep=-5;rep<20;rep++) {
            auto c=Clock::now();
            #pragma omp parallel for
            for(int i=0;i<n;i++) cpu[i]=query(xy[2*i],xy[2*i+1],base[i],tools.data(),count);
            double cm=elapsed(c);
            // 传输口径包含每次全部输入上传与结果下载；分配在计时外，单列说明。
            auto e=Clock::now();
            check(cudaMemcpy(dx,xy.data(),xy.size()*8,cudaMemcpyHostToDevice));
            check(cudaMemcpy(db,base.data(),n*8,cudaMemcpyHostToDevice));
            check(cudaMemcpy(dt,tools.data(),count*sizeof(Tool),cudaMemcpyHostToDevice));
            check(cudaEventRecord(start)); sweep<<<(n+255)/256,256>>>(dx,db,dt,count,out,n);
            check(cudaGetLastError()); check(cudaEventRecord(end));check(cudaEventSynchronize(end));
            float km;check(cudaEventElapsedTime(&km,start,end));
            check(cudaMemcpy(gpu.data(),out,n*8,cudaMemcpyDeviceToHost));
            double em=elapsed(e);
            if(rep>=0) { ct.push_back(cm);kt.push_back(km);et.push_back(em); }
        }
        double error=0; int mismatch=0;
        for(int i=0;i<n;i++) { if(!std::isfinite(gpu[i])) return 4; error=std::max(error,std::abs(cpu[i]-gpu[i])); if((cpu[i]<base[i])!=(gpu[i]<base[i])) mismatch++; }
        if(error>1e-10 || mismatch) return 5;
        if(!first) printf(",\n");first=false;
        printf("{\"points\":%d,\"segments\":%d,\"max_abs_error_mm\":%.17g,\"classification_mismatch\":%d,",n,count,error,mismatch);
        auto emit=[](const char* name,const std::vector<double>& v) { printf("\"%s\":[",name); for(size_t i=0;i<v.size();i++) printf("%s%.9g",i?",":"",v[i]); printf("]"); };
        emit("cpu_ms",ct);printf(",");emit("kernel_ms",kt);printf(",");emit("transfer_inclusive_ms",et);printf("}");fflush(stdout);
        check(cudaFree(dx));check(cudaFree(db));check(cudaFree(out));check(cudaFree(dt));check(cudaEventDestroy(start));check(cudaEventDestroy(end));
    }
    printf("\n]}\n");return 0;
}
