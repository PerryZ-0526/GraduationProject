// 独立扩展只接收连续CUDA FP64三角数组，不在接口降精度。
#include <torch/extension.h>
#include "torchcumesh2sdf.h"
#include "main.cuh"

bool registeredExitHooks = false;

at::Tensor get_sdf(const at::Tensor tris, const int R, const float band, const int B)
{
    TORCH_CHECK(tris.is_cuda() && tris.is_contiguous() && tris.scalar_type() == at::kDouble && tris.dim() == 3, "需要连续CUDA FP64三角数组");
    assert(tris.sizes()[1] == 3);
    assert(tris.sizes()[2] == 3);
    auto rast = rasterize_tris((double3*)tris.data_ptr<double>(), tris.sizes()[0], R, band, B, true);
    fill_signs((double3*)tris.data_ptr<double>(), R, rast, true);
    int device;
    CHECK_CUDA(cudaGetDevice(&device));
    auto options = torch::TensorOptions().dtype(torch::kFloat32).device(torch::kCUDA, device);
    at::Tensor result = torch::from_blob(rast.gridDist, { R, R, R }, options).clone();
    if (!registeredExitHooks)
    {
        registeredExitHooks = true;
        py::module_::import("atexit").attr("register")(py::module_::import("cut_sdf_fp64").attr("free_cached_memory"));
    }
    return result;
}

at::Tensor get_udf(const at::Tensor tris, const int R, const float band, const int B)
{
    TORCH_CHECK(tris.is_cuda() && tris.is_contiguous() && tris.scalar_type() == at::kDouble && tris.dim() == 3, "需要连续CUDA FP64三角数组");
    assert(tris.sizes()[1] == 3);
    assert(tris.sizes()[2] == 3);
    auto rast = rasterize_tris((double3*)tris.data_ptr<double>(), tris.sizes()[0], R, band, B, true);
    int device;
    CHECK_CUDA(cudaGetDevice(&device));
    auto options = torch::TensorOptions().dtype(torch::kFloat32).device(torch::kCUDA, device);
    at::Tensor result = torch::from_blob(rast.gridDist, { R, R, R }, options).clone();
    if (!registeredExitHooks)
    {
        registeredExitHooks = true;
        py::module_::import("atexit").attr("register")(py::module_::import("cut_sdf_fp64").attr("free_cached_memory"));
    }
    return result;
}

at::Tensor get_collide(const at::Tensor tris, const int R, const float band, const int B)
{
    TORCH_CHECK(tris.is_cuda() && tris.is_contiguous() && tris.scalar_type() == at::kDouble && tris.dim() == 3, "需要连续CUDA FP64三角数组");
    assert(tris.sizes()[1] == 3);
    assert(tris.sizes()[2] == 3);
    auto rast = rasterize_tris((double3*)tris.data_ptr<double>(), tris.sizes()[0], R, band, B, true);
    int device;
    CHECK_CUDA(cudaGetDevice(&device));
    auto options = torch::TensorOptions().dtype(torch::kBool).device(torch::kCUDA, device);
    at::Tensor result = torch::from_blob(rast.gridCollide, { R, R, R, 3 }, options).clone();
    if (!registeredExitHooks)
    {
        registeredExitHooks = true;
        py::module_::import("atexit").attr("register")(py::module_::import("cut_sdf_fp64").attr("free_cached_memory"));
    }
    return result;
}

void free_cached_memory()
{
    clear_raster_alloc_cache();
    clear_sign_alloc_cache();
}
