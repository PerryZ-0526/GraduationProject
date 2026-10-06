// 布尔来源诊断适配器：复用作者运算，按实际输出面序导出操作数位。
#include <geogram/basic/common.h>
#include <geogram/basic/attributes.h>
#include <geogram/basic/command_line.h>
#include <geogram/basic/command_line_args.h>
#include <geogram/mesh/mesh.h>
#include <geogram/mesh/mesh_io.h>
#include <geogram/mesh/mesh_surface_intersection.h>
#include <fstream>
#include <iomanip>
#include <string>
#include <vector>

int main(int argc, char** argv) {
    std::string operation = "A-B";
    GEO::MeshBooleanOperationFlags flags = GEO::MESH_BOOL_OPS_DEFAULT;
    std::vector<const char*> positional;
    for(int i = 1; i < argc; ++i) {
        const std::string argument(argv[i]);
        if(argument == "--no-simplify") {
            flags = GEO::MESH_BOOL_OPS_NO_SIMPLIFY;
        } else if(argument == "--verbose") {
            // 仅启用作者分阶段日志，差集和无简化参数保持。
            flags = static_cast<GEO::MeshBooleanOperationFlags>(int(flags) | int(GEO::MESH_BOOL_OPS_VERBOSE));
        } else if(argument == "--operation" && i + 1 < argc) {
            const std::string requested(argv[++i]);
            if(requested == "difference") operation = "A-B";
            else if(requested == "intersection") operation = "A*B";
            else if(requested == "union") operation = "A+B";
            else return 2;
        } else {
            positional.push_back(argv[i]);
        }
    }
    if(positional.size() != 4) return 2;
    GEO::initialize(GEO::GEOGRAM_INSTALL_ALL);
    GEO::CmdLine::import_arg_group("standard");
    GEO::CmdLine::import_arg_group("algo");
    GEO::CmdLine::set_arg("sys:max_threads", 4);
    GEO::Mesh parent, tool, result;
    if(!GEO::mesh_load(positional[0], parent) || !GEO::mesh_load(positional[1], tool)) return 3;
    GEO::mesh_boolean_operation(result, parent, tool, operation, flags);
    GEO::Attribute<GEO::index_t> bits;
    bits.bind_if_is_defined(result.facets.attributes(), "operand_bit");
    if(!bits.is_bound()) return 5;
    std::ofstream mesh(positional[2]), labels(positional[3]);
    mesh << std::setprecision(17);
    for(GEO::index_t v = 0; v < result.vertices.nb(); ++v) {
        const double* p = result.vertices.point_ptr(v);
        mesh << "v " << p[0] << ' ' << p[1] << ' ' << p[2] << '\n';
    }
    labels << "{\"schema_version\":1,\"operation\":\"" << operation
           << "\",\"no_simplify\":" << ((flags == GEO::MESH_BOOL_OPS_NO_SIMPLIFY) ? "true" : "false")
           << ",\"operand_bits\":[";
    for(GEO::index_t f = 0; f < result.facets.nb(); ++f) {
        if(result.facets.nb_vertices(f) != 3) return 4;
        mesh << "f " << result.facets.vertex(f, 0) + 1 << ' '
             << result.facets.vertex(f, 1) + 1 << ' ' << result.facets.vertex(f, 2) + 1 << '\n';
        if(f != 0) labels << ',';
        labels << bits[f];
    }
    labels << "]}\n";
    return (mesh && labels) ? 0 : 6;
}
