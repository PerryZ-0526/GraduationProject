// 原生布尔运算计时入口：加载、内核生成和保存分开记录，输出不接Python修复。
#include <geogram/basic/common.h>
#include <geogram/basic/command_line.h>
#include <geogram/basic/command_line_args.h>
#include <geogram/mesh/mesh.h>
#include <geogram/mesh/mesh_io.h>
#include <geogram/mesh/mesh_surface_intersection.h>
#include <chrono>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <string>

int main(int argc, char** argv) {
    if(argc != 4 && argc != 5) return 2;
    GEO::initialize(GEO::GEOGRAM_INSTALL_ALL);
    GEO::CmdLine::import_arg_group("standard");
    GEO::CmdLine::import_arg_group("algo");
    GEO::CmdLine::set_arg("sys:max_threads", 4);
    const bool simplify = argc == 4;
    GEO::Mesh parent, tool, result;
    using Clock = std::chrono::steady_clock;
    auto start = Clock::now();
    if(!GEO::mesh_load(argv[1], parent) || !GEO::mesh_load(argv[2], tool)) return 3;
    auto loaded = Clock::now();
    // 诊断执行器只开启作者阶段日志，库、算法和输入不改变，耗时不混入正式配对。
    GEO::mesh_boolean_operation(result, parent, tool, "A-B", GEO::MeshBooleanOperationFlags(
        (simplify ? GEO::MESH_BOOL_OPS_DEFAULT : GEO::MESH_BOOL_OPS_NO_SIMPLIFY) | GEO::MESH_BOOL_OPS_VERBOSE));
    auto generated = Clock::now();
    // 保存全部返回面与双精度坐标，保留极小面用于独立评价。
    std::ofstream out(argv[3]);
    out << std::setprecision(17);
    for(GEO::index_t v=0; v<result.vertices.nb(); ++v) {
        const double* p = result.vertices.point_ptr(v);
        out << "v " << p[0] << ' ' << p[1] << ' ' << p[2] << '\n';
    }
    for(GEO::index_t f=0; f<result.facets.nb(); ++f) {
        if(result.facets.nb_vertices(f) != 3) return 4;
        out << "f " << result.facets.vertex(f,0)+1 << ' '
            << result.facets.vertex(f,1)+1 << ' ' << result.facets.vertex(f,2)+1 << '\n';
    }
    out.close();
    auto saved = Clock::now();
    auto ms = [](auto a, auto b) {return std::chrono::duration<double,std::milli>(b-a).count();};
    std::cout << std::setprecision(17) << "NATIVE_RESULT {\"load_ms\":" << ms(start,loaded)
        << ",\"boolean_ms\":" << ms(loaded,generated) << ",\"save_ms\":" << ms(generated,saved)
        << ",\"faces\":" << result.facets.nb() << ",\"vertices\":" << result.vertices.nb()
        << ",\"simplify\":" << (simplify ? "true" : "false") << "}" << std::endl;
    return out ? 0 : 5;
}
