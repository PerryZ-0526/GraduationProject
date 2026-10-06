// 在同一私有库中核对排序开关：面序、方向、来源位及角属性均须一致。
#include <geogram/basic/common.h>
#include <geogram/basic/command_line.h>
#include <geogram/basic/command_line_args.h>
#include <geogram/basic/attributes.h>
#include <geogram/basic/logger.h>
#include <geogram/mesh/mesh.h>
#include <geogram/mesh/mesh_repair.h>
#include <chrono>
#include <iostream>
#include <stdexcept>
#include <vector>

using namespace GEO;
using Snapshot = std::vector<index_t>;

Snapshot snapshot(Mesh& mesh) {
    Attribute<index_t> bits(mesh.facets.attributes(), "operand_bit");
    Attribute<index_t> tags(mesh.facet_corners.attributes(), "probe_corner");
    Snapshot result = {mesh.vertices.nb(), mesh.facets.nb()};
    for(index_t f: mesh.facets) {
        result.push_back(mesh.facets.nb_vertices(f));
        result.push_back(bits[f]);
        for(index_t c = mesh.facets.corners_begin(f); c < mesh.facets.corners_end(f); ++c) {
            result.push_back(mesh.facet_corners.vertex(c));
            result.push_back(tags[c]);
        }
    }
    return result;
}

void create_case(Mesh& mesh, unsigned which) {
    // 补查作者65535面并行分支；大网格重复及退化仍须与排序模式一致。
    mesh.vertices.create_vertices(which >= 8 ? (which == 8 ? 50002 : 70002) : 8);
    for(index_t v: mesh.vertices) {
        mesh.vertices.point_ptr(v)[0] = double(v);
        mesh.vertices.point_ptr(v)[1] = double((v*v) % 137);
        mesh.vertices.point_ptr(v)[2] = 0.0;
    }
    std::vector<std::vector<index_t>> faces;
    switch(which) {
        case 0: faces = {{2,0,1},{3,1,2},{2,4,3}}; break;
        case 1: faces = {{2,0,1},{1,2,0},{3,4,5}}; break;
        case 2: faces = {{0,1,2},{2,1,0},{3,4,5}}; break;
        case 3: faces = {{0,1,2},{1,2,0},{2,1,0}}; break;
        case 4: faces = {{0,0,1},{1,0,0},{2,3,4}}; break;
        case 5: faces = {{3,0,1,2},{4,5,6}}; break;
        case 6: faces = {{0,1,1,2,3},{4,5,6}}; break;
        case 7: break;
        case 8:
            for(index_t f=0; f<50000; ++f) faces.push_back({f+2,f,f+1});
            break;
        case 9:
        case 10:
        case 11:
            for(index_t f=0; f<70000; ++f) faces.push_back({f+2,f,f+1});
            if(which == 10) faces.push_back({0,1,2});
            if(which == 11) faces.push_back({0,0,1});
            break;
    }
    for(const auto& row: faces) {
        index_t f = mesh.facets.create_polygon(index_t(row.size()));
        for(index_t i=0; i<row.size(); ++i) mesh.facets.set_vertex(f,i,row[i]);
    }
    Attribute<index_t> bits(mesh.facets.attributes(), "operand_bit");
    for(index_t f: mesh.facets) bits[f] = which == 2 ? 1 : (f%3)+1;
    Attribute<index_t> tags(mesh.facet_corners.attributes(), "probe_corner");
    for(index_t c=0; c<mesh.facet_corners.nb(); ++c) tags[c] = c+1000;
}

int main() {
    GEO::initialize(GEO::GEOGRAM_INSTALL_ALL);
    CmdLine::import_arg_group("standard");
    CmdLine::import_arg_group("algo");
    CmdLine::declare_arg("algo:linear_unique_facets", false, "Linear unique triangle scan");
    CmdLine::set_arg("sys:max_threads", 4);
    Logger::instance()->set_quiet(true);
    std::cout << "{\"cases\":[";
    // 首九类保留原控制，再补三类超过并行阈值的大网格控制。
    for(unsigned which=0; which<12; ++which) {
        Mesh source;
        create_case(source, which);
        std::vector<double> times[2];
        for(unsigned round=0; round<21; ++round) {
            Snapshot saved[2];
            for(unsigned position=0; position<2; ++position) {
                unsigned mode = (position + round) % 2;
                Mesh mesh;
                mesh.copy(source);
                CmdLine::set_arg("algo:linear_unique_facets", mode ? "true" : "false");
                // 只计作者坏面处理本体，不把网格复制和结果核对计入组件耗时。
                auto start = std::chrono::steady_clock::now();
                mesh_remove_bad_facets_no_check(mesh, true);
                double ms = std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-start).count();
                saved[mode] = snapshot(mesh);
                if(round) times[mode].push_back(ms);
            }
            if(saved[0] != saved[1]) throw std::runtime_error("cleanup output differs");
        }
        if(which) std::cout << ',';
        std::cout << "{\"case\":" << which << ",\"pairs\":21,\"identical\":true,\"times_ms\":[";
        for(unsigned mode=0; mode<2; ++mode) {
            if(mode) std::cout << ',';
            std::cout << '[';
            for(unsigned i=0; i<times[mode].size(); ++i) {
                if(i) std::cout << ',';
                std::cout << times[mode][i];
            }
            std::cout << ']';
        }
        std::cout << "]}";
    }
    std::cout << "]}" << std::endl;
}
