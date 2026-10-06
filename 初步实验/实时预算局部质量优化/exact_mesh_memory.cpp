// 完整精确嵌入核查的内存接口，不通过OBJ和远端进程发布网格。
#include <CGAL/Exact_predicates_exact_constructions_kernel.h>
#include <CGAL/Surface_mesh.h>
#include <CGAL/Polygon_mesh_processing/self_intersections.h>
#include <CGAL/boost/graph/helpers.h>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <vector>

using Kernel = CGAL::Exact_predicates_exact_constructions_kernel;
using Mesh = CGAL::Surface_mesh<Kernel::Point_3>;
using Clock = std::chrono::steady_clock;
#ifdef _WIN32
#define EXACT_MEMORY_API extern "C" __declspec(dllexport)
#else
#define EXACT_MEMORY_API extern "C" __attribute__((visibility("default")))
#endif
static double milliseconds(Clock::time_point start) {
    return std::chrono::duration<double,std::milli>(Clock::now()-start).count();
}
// 两个平台共享同一完整精确判据，仅导出方式不同。
EXACT_MEMORY_API int audit_arrays(
    const double* coordinates, std::uint64_t nv, const std::int64_t* facets,
    std::uint64_t nf, std::int64_t* result, double* timings) {
    try {
        for(int i=0;i<8;++i) result[i]=0;
        Mesh mesh;std::vector<Mesh::Vertex_index> vertices;vertices.reserve(nv);
        auto start=Clock::now();
        for(std::uint64_t i=0;i<nv;++i) {
            const double* p=coordinates+3*i;
            if(!std::isfinite(p[0]) || !std::isfinite(p[1]) || !std::isfinite(p[2])) return 1;
            vertices.push_back(mesh.add_vertex(Kernel::Point_3(p[0],p[1],p[2])));
        }
        std::int64_t degenerate=0;
        for(std::uint64_t i=0;i<nf;++i) {
            const auto* f=facets+3*i;
            for(int k=0;k<3;++k) if(f[k]<0 || std::uint64_t(f[k])>=nv) return 1;
            if(mesh.add_face(vertices[f[0]],vertices[f[1]],vertices[f[2]])==Mesh::null_face()) {
                result[0]=1;return 0;
            }
        }
        timings[0]=milliseconds(start);start=Clock::now();
        for(std::uint64_t i=0;i<nf;++i) {
            const auto* f=facets+3*i;
            if(CGAL::collinear(mesh.point(vertices[f[0]]),mesh.point(vertices[f[1]]),mesh.point(vertices[f[2]]))) ++degenerate;
        }
        timings[1]=milliseconds(start);start=Clock::now();
        std::vector<std::pair<Mesh::Face_index,Mesh::Face_index>> intersections;
        CGAL::Polygon_mesh_processing::self_intersections(mesh,std::back_inserter(intersections));
        bool closed=CGAL::is_closed(mesh);
        timings[2]=milliseconds(start);
        result[0]=1;result[1]=1;result[2]=nv;result[3]=nf;
        result[4]=closed;result[5]=intersections.size();result[7]=degenerate;
        result[6]=closed && intersections.empty() && !degenerate && nf>0;
        return 0;
    } catch(...) {
        return 2;
    }
}
