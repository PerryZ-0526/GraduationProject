// 在完整闭合网格上调用CGAL局部重网格，保留固定外部和来源交界。
#include <CGAL/Exact_predicates_inexact_constructions_kernel.h>
#include <CGAL/Surface_mesh.h>
#include <CGAL/boost/graph/IO/polygon_mesh_io.h>
#include <CGAL/Polygon_mesh_processing/remesh.h>
#include <CGAL/Polygon_mesh_processing/compute_normal.h>
#include <fstream>
#include <iomanip>
#include <vector>
#include <cmath>

using K = CGAL::Exact_predicates_inexact_constructions_kernel;
using Mesh = CGAL::Surface_mesh<K::Point_3>;
namespace PMP = CGAL::Polygon_mesh_processing;

int main(int argc, char** argv) {
    if(argc != 6) return 2;
    Mesh mesh;
    if(!CGAL::IO::read_polygon_mesh(argv[1], mesh) || !CGAL::is_triangle_mesh(mesh) || !CGAL::is_closed(mesh)) return 3;
    auto active = mesh.add_property_map<Mesh::Face_index, bool>("f:active", false).first;
    auto fixed = mesh.add_property_map<Mesh::Vertex_index, bool>("v:fixed", false).first;
    auto ids = mesh.add_property_map<Mesh::Vertex_index, int>("v:original", -1).first;
    auto edge_fixed = mesh.add_property_map<Mesh::Edge_index, bool>("e:fixed", false).first;
    auto bits = mesh.add_property_map<Mesh::Face_index, int>("f:source", 0).first;
    std::ifstream mask(argv[2]);
    size_t nv, nf;
    int protect_boundary;
    mask >> nv >> nf >> protect_boundary;
    if(nv != mesh.number_of_vertices() || nf != mesh.number_of_faces()) return 4;
    for(auto v: mesh.vertices()) {
        int value;
        mask >> value;
        fixed[v] = value != 0;
        ids[v] = static_cast<int>(v.idx());
    }
    std::vector<Mesh::Face_index> selected;
    for(auto f: mesh.faces()) {
        int value, bit;
        mask >> value >> bit;
        active[f] = value != 0;
        bits[f] = bit;
        if(active[f]) selected.push_back(f);
    }
    if(!mask) return 5;
    // 保护活动边界、来源交界和45度以上锐边；只对活动面所接边做约束。
    double max_protected = 0.0;
    for(auto edge: mesh.edges()) {
        auto h = mesh.halfedge(edge);
        auto f = mesh.face(h), g = mesh.face(mesh.opposite(h));
        if(!active[f] && !active[g]) continue;
        bool protect = (protect_boundary && active[f] != active[g]) || bits[f] != bits[g];
        auto n = PMP::compute_face_normal(f, mesh), m = PMP::compute_face_normal(g, mesh);
        protect = protect || CGAL::to_double(n * m) < std::cos(45.0 * std::acos(-1.0) / 180.0);
        edge_fixed[edge] = protect;
        if(protect) {
            fixed[mesh.source(h)] = true;
            fixed[mesh.target(h)] = true;
            max_protected = std::max(max_protected, std::sqrt(CGAL::to_double(
                CGAL::squared_distance(mesh.point(mesh.source(h)), mesh.point(mesh.target(h))))));
        }
    }
    // 保护边不允许细分；提高目标长度满足作者算法的长约束边前提，单列实际值。
    double requested = std::stod(argv[4]);
    double length = std::max(requested, 0.76 * max_protected);
    if(length <= 0.0 || !std::isfinite(length)) return 6;
    if(!selected.empty()) {
        PMP::isotropic_remeshing(selected, length, mesh,
            CGAL::parameters::number_of_iterations(3).face_patch_map(active)
                .edge_is_constrained_map(edge_fixed).vertex_is_constrained_map(fixed)
                .protect_constraints(protect_boundary != 0));
    }
    mesh.collect_garbage();
    std::ofstream obj(argv[3]), metadata(argv[5]);
    obj << std::setprecision(17);
    metadata << std::setprecision(17) << length << ' ' << max_protected << '\n';
    for(auto v: mesh.vertices()) {
        const auto& p = mesh.point(v);
        obj << "v " << p.x() << ' ' << p.y() << ' ' << p.z() << '\n';
        metadata << ids[v] << ' ' << fixed[v] << '\n';
    }
    for(auto f: mesh.faces()) {
        obj << 'f';
        for(auto v: CGAL::vertices_around_face(mesh.halfedge(f), mesh)) obj << ' ' << v.idx() + 1;
        obj << '\n';
    }
    return obj && metadata ? 0 : 7;
}
