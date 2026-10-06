// 常驻内存布尔接口：只改变数据传递方式，沿用作者默认差集和来源属性。
#include <geogram/basic/common.h>
#include <geogram/basic/attributes.h>
#include <geogram/basic/command_line.h>
#include <geogram/basic/command_line_args.h>
#include <geogram/basic/logger.h>
#include <geogram/mesh/mesh.h>
#include <geogram/mesh/mesh_surface_intersection.h>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <limits>
#include <memory>
#include <mutex>
#include <stdexcept>
#include <string>

namespace {
std::mutex operation_mutex;
bool initialized = false;
using Clock = std::chrono::steady_clock;
double elapsed(Clock::time_point t) {
    return std::chrono::duration<double, std::milli>(Clock::now()-t).count();
}
void load_arrays(GEO::Mesh& mesh, const double* v, uint64_t nv,
                 const int64_t* f, uint64_t nf) {
    if(!v || !f || !nv || !nf || nv > std::numeric_limits<GEO::index_t>::max()
       || nf > std::numeric_limits<GEO::index_t>::max()) {
        throw std::invalid_argument("invalid mesh counts");
    }
    mesh.vertices.create_vertices(GEO::index_t(nv));
    for(uint64_t i=0; i<nv; ++i) {
        for(int k=0; k<3; ++k) {
            if(!std::isfinite(v[3*i+k])) throw std::invalid_argument("nonfinite vertex");
            mesh.vertices.point_ptr(GEO::index_t(i))[k] = v[3*i+k];
        }
    }
    mesh.facets.create_triangles(GEO::index_t(nf));
    for(uint64_t i=0; i<nf; ++i) {
        for(int k=0; k<3; ++k) {
            if(f[3*i+k]<0 || uint64_t(f[3*i+k])>=nv) throw std::invalid_argument("invalid index");
            mesh.facets.set_vertex(GEO::index_t(i), k, GEO::index_t(f[3*i+k]));
        }
    }
    mesh.facets.connect();
}
}

// Linux实例与Windows本机编译相同内存接口，不借用身份未绑定的旧远端程序。
#ifdef _WIN32
#define MEMORY_API extern "C" __declspec(dllexport)
#else
#define MEMORY_API extern "C" __attribute__((visibility("default")))
#endif
MEMORY_API void* difference_arrays(
    const double* av, uint64_t anv, const int64_t* af, uint64_t anf,
    const double* bv, uint64_t bnv, const int64_t* bf, uint64_t bnf,
    uint64_t* counts, double* times, char* error, uint64_t error_size, int no_simplify) {
    // 作者全局初始化和参数共享，布尔调用串行，结果句柄由调用方独占。
    std::lock_guard<std::mutex> lock(operation_mutex);
    try {
        auto start = Clock::now();
        if(!initialized) {
            GEO::initialize(GEO::GEOGRAM_INSTALL_ALL);
            GEO::CmdLine::import_arg_group("standard");
            GEO::CmdLine::import_arg_group("algo");
            GEO::CmdLine::set_arg("sys:max_threads", 4);
            GEO::Logger::instance()->set_quiet(true);
            initialized = true;
        }
        times[0] = elapsed(start);
        start = Clock::now();
        GEO::Mesh a, b;
        load_arrays(a, av, anv, af, anf);
        load_arrays(b, bv, bnv, bf, bnf);
        times[1] = elapsed(start);
        auto result = std::make_unique<GEO::Mesh>();
        start = Clock::now();
        // 完整来源对照显式关闭作者共面简化；默认模式继续保持旧接口结果。
        auto flags = no_simplify ? GEO::MESH_BOOL_OPS_NO_SIMPLIFY : GEO::MESH_BOOL_OPS_DEFAULT;
        GEO::mesh_boolean_operation(*result, a, b, "A-B", flags);
        times[2] = elapsed(start);
        GEO::Attribute<GEO::index_t> bits;
        bits.bind_if_is_defined(result->facets.attributes(), "operand_bit");
        if(!bits.is_bound()) throw std::runtime_error("missing operand_bit");
        for(GEO::index_t i=0; i<result->facets.nb(); ++i) {
            if(result->facets.nb_vertices(i)!=3) throw std::runtime_error("nontriangle output");
        }
        counts[0] = result->vertices.nb();
        counts[1] = result->facets.nb();
        return result.release();
    } catch(const std::exception& e) {
        if(error && error_size) {
            std::strncpy(error, e.what(), size_t(error_size-1));
            error[error_size-1] = 0;
        }
        return nullptr;
    } catch(...) {
        if(error && error_size) {
            std::strncpy(error, "unknown Geogram failure", size_t(error_size-1));
            error[error_size-1] = 0;
        }
        return nullptr;
    }
}

MEMORY_API void copy_result(void* handle, double* v, int64_t* f, int64_t* bits_out) {
    auto& mesh = *static_cast<GEO::Mesh*>(handle);
    GEO::Attribute<GEO::index_t> bits(mesh.facets.attributes(), "operand_bit");
    for(GEO::index_t i=0; i<mesh.vertices.nb(); ++i) {
        std::memcpy(v+3*i, mesh.vertices.point_ptr(i), 3*sizeof(double));
    }
    for(GEO::index_t i=0; i<mesh.facets.nb(); ++i) {
        for(int k=0; k<3; ++k) f[3*i+k] = mesh.facets.vertex(i, k);
        bits_out[i] = bits[i];
    }
}
MEMORY_API void release_result(void* handle) {
    delete static_cast<GEO::Mesh*>(handle);
}
