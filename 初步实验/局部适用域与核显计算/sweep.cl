#pragma OPENCL EXTENSION cl_khr_fp64 : enable
#pragma OPENCL FP_CONTRACT OFF
// 每个工作项计算一个查询点；双精度下包络不包含原骨面定位或网格验收。
__kernel void sweep(__global const double2 *xy, __global const double *base,
                    __global const double *tools, const int count, __global double *out) {
    int i = get_global_id(0);
    double2 p = xy[i];
    double value = base[i];
    for (int j = 0; j < count; ++j) {
        int k = j * 6;
        double2 a = (double2)(tools[k], tools[k+1]);
        double2 b = (double2)(tools[k+2], tools[k+3]);
        double2 d = b-a;
        double length2 = dot(d, d);
        double t = length2 == 0.0 ? 0.0 : clamp(dot(p-a, d)/length2, 0.0, 1.0);
        double2 residual = p-a-t*d;
        double squared = dot(residual, residual);
        double radius = tools[k+4];
        if (squared <= radius*radius)
            value = fmin(value, tools[k+5]-sqrt(fmax(0.0, radius*radius-squared)));
    }
    out[i] = value;
}
