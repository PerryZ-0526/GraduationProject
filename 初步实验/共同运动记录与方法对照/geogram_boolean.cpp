// Thin experiment adapter: Geogram's default mesh difference with FP64 OBJ I/O.
#include <geogram/basic/common.h>
#include <geogram/basic/command_line.h>
#include <geogram/basic/command_line_args.h>
#include <geogram/mesh/mesh.h>
#include <geogram/mesh/mesh_io.h>
#include <geogram/mesh/mesh_surface_intersection.h>

#include <fstream>
#include <iomanip>

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
    if(argc != 4) {
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
        !GEO::mesh_load(argv[1], minuend)
        || !GEO::mesh_load(argv[2], subtrahend)
    ) {
        return 3;
    }
    GEO::mesh_difference(
        result,
        minuend,
        subtrahend,
        GEO::MESH_BOOL_OPS_DEFAULT
    );
    return save_double_obj(result, argv[3]) ? 0 : 4;
}
