// Geogram布尔运算薄适配层：保留FP64 OBJ输出并暴露作者已有的运算选项。
#include <geogram/basic/common.h>
#include <geogram/basic/command_line.h>
#include <geogram/basic/command_line_args.h>
#include <geogram/mesh/mesh.h>
#include <geogram/mesh/mesh_io.h>
#include <geogram/mesh/mesh_surface_intersection.h>

#include <fstream>
#include <iomanip>
#include <string>
#include <vector>

bool save_double_obj(const GEO::Mesh& mesh, const char* filename) {
    std::ofstream output(filename);
    output << std::setprecision(17);
    for(GEO::index_t vertex = 0; vertex < mesh.vertices.nb(); ++vertex) {
        const double* point = mesh.vertices.point_ptr(vertex);
        output << "v " << point[0] << ' ' << point[1] << ' '
               << point[2] << '\n';
    }
    for(GEO::index_t facet = 0; facet < mesh.facets.nb(); ++facet) {
        if(mesh.facets.nb_vertices(facet) != 3) {
            return false;
        }
        output << "f " << mesh.facets.vertex(facet, 0) + 1 << ' '
               << mesh.facets.vertex(facet, 1) + 1 << ' '
               << mesh.facets.vertex(facet, 2) + 1 << '\n';
    }
    return bool(output);
}

int main(int argc, char** argv) {
    std::string operation = "A-B";
    GEO::MeshBooleanOperationFlags flags = GEO::MESH_BOOL_OPS_DEFAULT;
    std::vector<const char*> positional;
    for(int i = 1; i < argc; ++i) {
        const std::string argument(argv[i]);
        if(argument == "--no-simplify") {
            flags = GEO::MESH_BOOL_OPS_NO_SIMPLIFY;
        } else if(argument == "--operation" && i + 1 < argc) {
            const std::string requested(argv[++i]);
            if(requested == "difference") {
                operation = "A-B";
            } else if(requested == "intersection") {
                operation = "A*B";
            } else if(requested == "union") {
                operation = "A+B";
            } else {
                return 2;
            }
        } else {
            positional.push_back(argv[i]);
        }
    }
    if(positional.size() != 3) {
        return 2;
    }
    GEO::initialize(GEO::GEOGRAM_INSTALL_ALL);
    GEO::CmdLine::import_arg_group("standard");
    GEO::CmdLine::import_arg_group("algo");
    GEO::CmdLine::set_arg("sys:max_threads", 4);
    GEO::Mesh minuend;
    GEO::Mesh subtrahend;
    GEO::Mesh result;
    if(
        !GEO::mesh_load(positional[0], minuend)
        || !GEO::mesh_load(positional[1], subtrahend)
    ) {
        return 3;
    }
    GEO::mesh_boolean_operation(
        result,
        minuend,
        subtrahend,
        operation,
        flags
    );
    return save_double_obj(result, positional[2]) ? 0 : 4;
}
