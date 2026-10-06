// 独立同编译配置FP32对照，仅重命名退出缓存清理模块，原数学与输入类型不变。
#include <torch/extension.h>
#include "torchcumesh2sdf.h"
#include "main.cuh"

bool registeredExitHooks = false;

at::Tensor get_sdf(const at::Tensor tris, const int R, const float band, const int B)
{
    assert(tris.sizes()[1] == 3);
    assert(tris.sizes()[2] == 3);
    auto rast = rasterize_tris((float3*)tris.data_ptr<float>(), tris.sizes()[0], R, band, B, true);
    fill_signs((float3*)tris.data_ptr<float>(), R, rast, true);
    int device;
    CHECK_CUDA(cudaGetDevice(&device));
    auto options = torch::TensorOptions().dtype(torch::kFloat32).device(torch::kCUDA, device);
    at::Tensor result = torch::from_blob(rast.gridDist, { R, R, R }, options).clone();
    if (!registeredExitHooks)
    {
        registeredExitHooks = true;
        py::module_::import("atexit").attr("register")(py::module_::import("cut_sdf_fp32_control").attr("free_cached_memory"));
    }
    return result;
}

at::Tensor get_udf(const at::Tensor tris, const int R, const float band, const int B)
{
    assert(tris.sizes()[1] == 3);
    assert(tris.sizes()[2] == 3);
    auto rast = rasterize_tris((float3*)tris.data_ptr<float>(), tris.sizes()[0], R, band, B, true);
    int device;
    CHECK_CUDA(cudaGetDevice(&device));
    auto options = torch::TensorOptions().dtype(torch::kFloat32).device(torch::kCUDA, device);
    at::Tensor result = torch::from_blob(rast.gridDist, { R, R, R }, options).clone();
    if (!registeredExitHooks)
    {
        registeredExitHooks = true;
        py::module_::import("atexit").attr("register")(py::module_::import("cut_sdf_fp32_control").attr("free_cached_memory"));
    }
    return result;
}

at::Tensor get_collide(const at::Tensor tris, const int R, const float band, const int B)
{
    assert(tris.sizes()[1] == 3);
    assert(tris.sizes()[2] == 3);
    auto rast = rasterize_tris((float3*)tris.data_ptr<float>(), tris.sizes()[0], R, band, B, true);
    int device;
    CHECK_CUDA(cudaGetDevice(&device));
    auto options = torch::TensorOptions().dtype(torch::kBool).device(torch::kCUDA, device);
    at::Tensor result = torch::from_blob(rast.gridCollide, { R, R, R, 3 }, options).clone();
    if (!registeredExitHooks)
    {
        registeredExitHooks = true;
        py::module_::import("atexit").attr("register")(py::module_::import("cut_sdf_fp32_control").attr("free_cached_memory"));
    }
    return result;
}

void free_cached_memory()
{
    clear_raster_alloc_cache();
    clear_sign_alloc_cache();
}
