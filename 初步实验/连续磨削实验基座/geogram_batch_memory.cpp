// 在同一冻结Geogram入口增加多工具差集，原两操作数接口及结果所有权保持。
#include "geogram_memory.cpp"

namespace {
void append_operand(GEO::Mesh& result,const GEO::Mesh& operand,GEO::index_t operand_id) {
    GEO::Attribute<GEO::index_t> bits(result.facets.attributes(),"operand_bit");
    if(operand.vertices.nb()>std::numeric_limits<GEO::index_t>::max()-result.vertices.nb() ||
       operand.facets.nb()>std::numeric_limits<GEO::index_t>::max()-result.facets.nb())
        throw std::invalid_argument("combined operand count overflow");
    GEO::index_t offset=result.vertices.create_vertices(operand.vertices.nb());
    for(GEO::index_t i=0;i<operand.vertices.nb();++i)
        std::memcpy(result.vertices.point_ptr(offset+i),operand.vertices.point_ptr(i),3*sizeof(double));
    for(GEO::index_t i=0;i<operand.facets.nb();++i) {
        GEO::index_t face=result.facets.create_triangle(offset+operand.facets.vertex(i,0),
            offset+operand.facets.vertex(i,1),offset+operand.facets.vertex(i,2));
        bits[face]=GEO::index_t(1)<<operand_id;
    }
}
}

MEMORY_API void* batch_difference_arrays(
    const double* av,uint64_t anv,const int64_t* af,uint64_t anf,
    const double* tool_vertices,const uint64_t* vertex_counts,
    const int64_t* tool_faces,const uint64_t* face_counts,uint64_t tool_count,
    uint64_t* counts,double* times,char* error,uint64_t error_size,int flags) {
    // 全部工具分别作为闭合操作数；不能把相交工具简单拼成一个已认证闭壳。
    std::lock_guard<std::mutex> lock(operation_mutex);
    try {
        if(!tool_count || tool_count>31 || tool_count>=8*sizeof(GEO::index_t))
            throw std::invalid_argument("batch requires 1..31 tool operands");
        auto start=Clock::now();
        if(!initialized) {
            GEO::initialize(GEO::GEOGRAM_INSTALL_ALL);
            GEO::CmdLine::import_arg_group("standard");GEO::CmdLine::import_arg_group("algo");
            GEO::CmdLine::set_arg("sys:max_threads",4);
            GEO::CmdLine::declare_arg("algo:certified_operands",false,"Certified closed embedded operands");
            GEO::Logger::instance()->set_quiet(true);initialized=true;
        }
        times[0]=elapsed(start);start=Clock::now();
        auto result=std::make_unique<GEO::Mesh>();GEO::Mesh bone;
        load_arrays(bone,av,anv,af,anf);append_operand(*result,bone,0);
        uint64_t vertex_offset=0,face_offset=0;std::string expression="x0-(";
        for(uint64_t i=0;i<tool_count;++i) {
            GEO::Mesh tool;load_arrays(tool,tool_vertices+3*vertex_offset,vertex_counts[i],
                tool_faces+3*face_offset,face_counts[i]);
            append_operand(*result,tool,GEO::index_t(i+1));
            vertex_offset+=vertex_counts[i];face_offset+=face_counts[i];
            if(i) expression+='+';expression+='x'+std::to_string(i+1);
        }
        expression+=')';times[1]=elapsed(start);start=Clock::now();
        GEO::CmdLine::set_arg("algo:certified_operands",(flags & 2) ? "true" : "false");
        GEO::MeshSurfaceIntersection intersection(*result);
        intersection.set_radial_sort(true);intersection.set_verbose(false);
        intersection.intersect();intersection.classify(expression);
        if(!(flags & 1)) intersection.simplify_coplanar_facets();
        times[2]=elapsed(start);
        for(GEO::index_t i=0;i<result->facets.nb();++i)
            if(result->facets.nb_vertices(i)!=3) throw std::runtime_error("nontriangle batch output");
        counts[0]=result->vertices.nb();counts[1]=result->facets.nb();return result.release();
    } catch(const std::exception& e) {
        if(error && error_size) {std::strncpy(error,e.what(),size_t(error_size-1));error[error_size-1]=0;}
        return nullptr;
    } catch(...) {
        if(error && error_size) {std::strncpy(error,"unknown batch failure",size_t(error_size-1));error[error_size-1]=0;}
        return nullptr;
    }
}
