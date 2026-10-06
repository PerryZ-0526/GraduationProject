#pragma once
// 双精度几何向量运算，仅用于输入三角形与网格查询位置。
inline __host__ __device__ double3 operator+(double3 a,double3 b){return make_double3(a.x+b.x,a.y+b.y,a.z+b.z);}
inline __host__ __device__ double3 operator-(double3 a,double3 b){return make_double3(a.x-b.x,a.y-b.y,a.z-b.z);}
inline __host__ __device__ double3 operator+(double3 a,double b){return make_double3(a.x+b,a.y+b,a.z+b);}
inline __host__ __device__ double3 operator*(double3 a,double b){return make_double3(a.x*b,a.y*b,a.z*b);}
inline __host__ __device__ double3 operator*(double a,double3 b){return b*a;}
inline __host__ __device__ double3 operator/(double3 a,double b){return a*(1.0/b);}
inline __host__ __device__ void operator-=(double3 &a,double3 b){a=a-b;}
inline __host__ __device__ double dot(double3 a,double3 b){return a.x*b.x+a.y*b.y+a.z*b.z;}
inline __host__ __device__ double3 cross(double3 a,double3 b){return make_double3(a.y*b.z-a.z*b.y,a.z*b.x-a.x*b.z,a.x*b.y-a.y*b.x);}
inline __host__ __device__ double3 normalize(double3 a){return a/sqrt(dot(a,a));}
inline __host__ __device__ double clamp(double a,double lo,double hi){return fmin(fmax(a,lo),hi);}
inline __host__ __device__ double3 lerp(double3 a,double3 b,double t){return a+(b-a)*t;}
