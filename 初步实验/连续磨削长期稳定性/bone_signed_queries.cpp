// 对保存FP64骨面执行精确内部判定与最近距离查询，距离仅以double输出。
#include <CGAL/Exact_predicates_exact_constructions_kernel.h>
#include <CGAL/Surface_mesh.h>
#include <CGAL/AABB_tree.h>
#include <CGAL/AABB_traits_3.h>
#include <CGAL/AABB_face_graph_triangle_primitive.h>
#include <CGAL/Side_of_triangle_mesh.h>
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
using Primitive = CGAL::AABB_face_graph_triangle_primitive<Mesh>;
using Traits = CGAL::AABB_traits_3<Kernel, Primitive>;
using Tree = CGAL::AABB_tree<Traits>;
int main(int argc, char** argv) {
    if (argc != 4) return 2;
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
            double x,y,z;
            if (!(stream>>x>>y>>z) || !std::isfinite(x) || !std::isfinite(y) || !std::isfinite(z)) return 2;
            // 精确表示输入OBJ解析后的二进制值，不恢复原始CT或布尔精确构造。
            vertices.push_back(mesh.add_vertex(Kernel::Point_3(x,y,z)));
        } else if (tag == "f") {
            std::array<std::string,3> tokens;
            std::string extra;
            if (!(stream>>tokens[0]>>tokens[1]>>tokens[2]) || stream>>extra) return 2;
            std::array<std::size_t,3> ids;
            for (int i=0;i<3;++i) {
                int id=std::stoi(tokens[i]);
                if (id<=0 || static_cast<std::size_t>(id)>vertices.size()) return 2;
                ids[i]=static_cast<std::size_t>(id-1);
            }
            if (mesh.add_face(vertices[ids[0]],vertices[ids[1]],vertices[ids[2]])==Mesh::null_face()) return 3;
        }
    }
    // 开放面、精确退化和全量自交均在建树查询前拒绝，不能假定射线符号适用。
    if (!CGAL::is_closed(mesh) || !CGAL::is_triangle_mesh(mesh) || mesh.number_of_faces()==0) return 3;
    for (auto face:mesh.faces()) {
        auto edge=mesh.halfedge(face);
        auto a=mesh.point(mesh.source(edge)), b=mesh.point(mesh.target(edge));
        auto c=mesh.point(mesh.target(mesh.next(edge)));
        if (Kernel::Triangle_3(a,b,c).is_degenerate()) return 3;
    }
    if (CGAL::Polygon_mesh_processing::does_self_intersect(mesh)) return 3;
    Tree tree(faces(mesh).first,faces(mesh).second,mesh);
    tree.build();
    tree.accelerate_distance_queries();
    CGAL::Side_of_triangle_mesh<Mesh,Kernel> side(tree);
    std::ifstream queries(argv[2],std::ios::binary|std::ios::ate);
    if (!queries || queries.tellg()%static_cast<std::streamoff>(3*sizeof(double))!=0) return 2;
    const std::size_t count=static_cast<std::size_t>(queries.tellg())/(3*sizeof(double));
    queries.seekg(0);
    std::ofstream output(argv[3],std::ios::binary);
    if (!output) return 2;
    std::size_t inside=0,outside=0,boundary=0,underflows=0;
    for (std::size_t i=0;i<count;++i) {
        std::array<double,3> coordinates;
        queries.read(reinterpret_cast<char*>(coordinates.data()),3*sizeof(double));
        for (double value:coordinates) if (!std::isfinite(value)) return 2;
        const Kernel::Point_3 point(coordinates[0],coordinates[1],coordinates[2]);
        const auto classification=side(point);
        const auto square=tree.squared_distance(point);
        const double magnitude=std::sqrt(CGAL::to_double(square));
        // 精确符号与double距离分别输出；不以任意下限掩盖零值或距离下溢。
        const double sign=classification==CGAL::ON_BOUNDED_SIDE ? -1.0 : classification==CGAL::ON_UNBOUNDED_SIDE ? 1.0 : 0.0;
        if (sign<0)++inside; else if(sign>0)++outside; else ++boundary;
        if (magnitude==0 && square!=0)++underflows;
        const std::array<double,2> result{sign*magnitude,sign};
        output.write(reinterpret_cast<const char*>(result.data()),2*sizeof(double));
    }
    output.flush();
    if (!output) return 2;
    std::cout<<"{\"queries\":"<<count<<",\"inside\":"<<inside<<",\"outside\":"<<outside<<",\"boundary\":"<<boundary<<",\"distance_double_underflows\":"<<underflows<<",\"source_vertices\":"<<mesh.number_of_vertices()<<",\"source_faces\":"<<mesh.number_of_faces()<<",\"kernel\":\"EPECK_on_stored_binary64\"}\n";
}
