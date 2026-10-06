#include "exact_self_intersection_indices.h"
#include <CGAL/Exact_predicates_exact_constructions_kernel.h>
#include <CGAL/Surface_mesh.h>
#include <CGAL/Polygon_mesh_processing/self_intersections.h>
#include <CGAL/boost/graph/helpers.h>
#include <cmath>
#include <numeric>

std::vector<unsigned int> exact_self_intersection_indices(
    const float* vertices, const int* faces, int n_vertices, int n_faces,
    bool& topology_valid)
{
    using K = CGAL::Exact_predicates_exact_constructions_kernel;
    using M = CGAL::Surface_mesh<K::Point_3>;
    M mesh;
    std::vector<M::Vertex_index> ids;
    std::vector<unsigned int> source_face_ids;
    topology_valid = true;
    auto invalid = [&]() {
        // 不合法中间状态使本轮所有折叠回退，包括已经标记删除的面。
        topology_valid = false;
        std::vector<unsigned int> result(n_faces);
        std::iota(result.begin(), result.end(), 0);
        return result;
    };
    for (int i = 0; i < n_vertices; ++i) {
        double x = vertices[3*i], y = vertices[3*i+1], z = vertices[3*i+2];
        if (!std::isfinite(x) || !std::isfinite(y) || !std::isfinite(z)) return invalid();
        ids.push_back(mesh.add_vertex(K::Point_3(x,y,z)));
    }
    for (int i = 0; i < n_faces; ++i) {
        const int* f = faces + 3*i;
        if (f[0] < 0) continue;
        for (int j = 0; j < 3; ++j) if (f[j] < 0 || f[j] >= n_vertices) return invalid();
        if (CGAL::collinear(mesh.point(ids[f[0]]),mesh.point(ids[f[1]]),mesh.point(ids[f[2]]))) return invalid();
        if (mesh.add_face(ids[f[0]],ids[f[1]],ids[f[2]]) == M::null_face()) return invalid();
        source_face_ids.push_back(i);
    }
    if (!mesh.number_of_faces() || !CGAL::is_closed(mesh)) return invalid();
    std::vector<std::pair<M::Face_index,M::Face_index>> intersections;
    CGAL::Polygon_mesh_processing::self_intersections(mesh,std::back_inserter(intersections));
    std::vector<unsigned int> result;
    for (auto pair : intersections) {
        // 保留每个精确相交对，映射回包含删除槽位的原GPU面编号。
        result.push_back(source_face_ids[pair.first.idx()]);
        result.push_back(source_face_ids[pair.second.idx()]);
    }
    return result;
}
