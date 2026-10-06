// 对保存OBJ的二进制FP64坐标执行CGAL全网格精确自交检查，不复用有限报警集合。
#include <CGAL/Exact_predicates_exact_constructions_kernel.h>
#include <CGAL/Surface_mesh.h>
#include <CGAL/Polygon_mesh_processing/self_intersections.h>
#include <CGAL/boost/graph/helpers.h>
#include <array>
#include <cmath>
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

using Kernel = CGAL::Exact_predicates_exact_constructions_kernel;
using Mesh = CGAL::Surface_mesh<Kernel::Point_3>;

int main(int argc, char** argv) {
    if (argc < 2 || argc > 3) return 2;
    std::ifstream input(argv[1]);
    if (!input) return 2;
    Mesh mesh;
    std::vector<Mesh::Vertex_index> vertices;
    std::string line;
    while (std::getline(input, line)) {
        std::istringstream stream(line);
        std::string tag;
        stream >> tag;
        if (tag == "v") {
            double x, y, z;
            if (!(stream >> x >> y >> z) || !std::isfinite(x) || !std::isfinite(y) || !std::isfinite(z)) return 2;
            // 先按协议解析为double，再由EPECK精确表示该二进制值，不能冒称恢复原始CSG精确构造。
            vertices.push_back(mesh.add_vertex(Kernel::Point_3(x, y, z)));
        } else if (tag == "f") {
            std::array<std::string, 3> tokens;
            std::string extra;
            if (!(stream >> tokens[0] >> tokens[1] >> tokens[2]) || (stream >> extra)) return 2;
            std::array<std::size_t, 3> ids;
            for (int i = 0; i < 3; ++i) {
                int id = std::stoi(tokens[i]);
                if (id <= 0 || static_cast<std::size_t>(id) > vertices.size()) return 2;
                ids[i] = static_cast<std::size_t>(id - 1);
            }
            if (mesh.add_face(vertices[ids[0]], vertices[ids[1]], vertices[ids[2]]) == Mesh::null_face()) {
                std::cout << "{\"parsed\":true,\"topology_valid\":false,\"embedded_closed\":false}\n";
                return 0;
            }
        }
    }
    std::vector<std::pair<Mesh::Face_index, Mesh::Face_index>> intersections;
    CGAL::Polygon_mesh_processing::self_intersections(mesh, std::back_inserter(intersections));
    // 诊断分支只追加实际相交面号，原完整嵌入判据保持。
    if (argc == 3) {
        std::ofstream pairs(argv[2]);
        pairs << "{\"intersection_face_pairs\":[";
        for (std::size_t i = 0; i < intersections.size(); ++i) {
            if (i) pairs << ',';
            pairs << '[' << intersections[i].first.idx() << ',' << intersections[i].second.idx() << ']';
        }
        pairs << "]}\n";
        if (!pairs) return 3;
    }
    bool closed = CGAL::is_closed(mesh);
    std::cout << "{\"parsed\":true,\"topology_valid\":true,\"vertices\":" << mesh.number_of_vertices()
              << ",\"faces\":" << mesh.number_of_faces() << ",\"closed\":" << (closed ? "true" : "false")
              << ",\"self_intersection_pairs\":" << intersections.size()
              << ",\"embedded_closed\":" << (closed && intersections.empty() && mesh.number_of_faces() > 0 ? "true" : "false")
              << ",\"kernel\":\"EPECK_on_stored_binary64\"}\n";
}
