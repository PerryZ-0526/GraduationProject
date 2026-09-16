// 实验适配层：复用Geogram默认布尔，仅将OBJ输出改为可往返的17位有效数字。
#include <geogram/basic/common.h>
#include <geogram/basic/command_line.h>
#include <geogram/basic/command_line_args.h>
#include <geogram/mesh/mesh.h>
#include <geogram/mesh/mesh_io.h>
#include <geogram/mesh/mesh_surface_intersection.h>
#include <fstream>
#include <iomanip>
#include <string>

bool save_double_obj(const GEO::Mesh& mesh, const char* filename) {
    std::ofstream out(filename);
    out << std::setprecision(17);
    for(GEO::index_t i=0;i<mesh.vertices.nb();i++) {
        const double* p=mesh.vertices.point_ptr(i);
        out << "v " << p[0] << ' ' << p[1] << ' ' << p[2] << '\n';
    }
    for(GEO::index_t i=0;i<mesh.facets.nb();i++) {
        if(mesh.facets.nb_vertices(i)!=3) return false;
        out << "f " << mesh.facets.vertex(i,0)+1 << ' ' << mesh.facets.vertex(i,1)+1 << ' ' << mesh.facets.vertex(i,2)+1 << '\n';
    }
    return bool(out);
}

int main(int argc, char** argv) {
    bool intersection=argc==5 && std::string(argv[1])=="--intersection";
    if(argc!=4 && !intersection) return 2;
    GEO::initialize(GEO::GEOGRAM_INSTALL_ALL);
    GEO::CmdLine::import_arg_group("standard");
    GEO::CmdLine::import_arg_group("algo");
    GEO::CmdLine::set_arg("sys:max_threads", 4);
    GEO::Mesh a,b,result;
    // 使用作者公开选项做共面简化消融，不修改上游求交或拓扑算法。
#ifdef GP_NO_SIMPLIFY
    auto flags=GEO::MESH_BOOL_OPS_NO_SIMPLIFY;
#else
    auto flags=GEO::MESH_BOOL_OPS_DEFAULT;
#endif
    // 复制模式验证整个输入网格的读写没有因十进制截断改变坐标或连接。
    if(std::string(argv[1])=="--copy") {
        if(!GEO::mesh_load(argv[2],a)) return 3;
        return save_double_obj(a,argv[3])?0:4;
    }
    // 原差集入口保持不变；交集仅用于恢复旧计划的阶段圆柱裁剪语义。
    int shift=intersection?1:0;
    if(!GEO::mesh_load(argv[1+shift],a) || !GEO::mesh_load(argv[2+shift],b)) return 3;
    if(intersection) GEO::mesh_intersection(result,a,b,flags);
    else GEO::mesh_difference(result,a,b,flags);
    return save_double_obj(result,argv[3+shift])?0:4;
}
