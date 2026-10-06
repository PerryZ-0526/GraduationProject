"""复制固定方法，仅添加可关闭输入捕获和终止栈，不更改原已评价算法。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json

here=Path(__file__).resolve().parent
source=here/'共面前清理固定原生候选封存'
output=here/'旋转窄缝原生终止现场诊断源码';output.mkdir()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
prior=json.loads((here/'440-固定原生主候选方法封存清单.json').read_text('utf8'))
names=[name for name in prior['files'] if name.startswith('mesh_surface_')]
for name in names:
    assert sha(source/name)==prior['files'][name]
    (output/name).write_bytes((source/name).read_bytes())
path=output/'mesh_surface_intersection_internal.cpp';code=path.read_text('utf8')
code=code.replace('#include <cstdio>','#include <cstdio>\n// 诊断文件逐次独立编号，不改变区域生成和所有接受判据。\n#include <atomic>\n#include <fstream>\n#include <iomanip>',1)
old='''    // Triangle初始化含共享全局常量，串行保护其调用；区域提取仍由Geogram并行执行。
    static std::mutex triangle_mutex;'''
new='''    // 仅诊断副本按环境开关保存精确送入Triangle的双精度数组，固定主算法没有该输出。
    static std::atomic<unsigned long> capture_counter(0);
    std::string capture_prefix;
    if(const char* dir=std::getenv("GEO_NATIVE_FAILURE_CAPTURE")) {
        capture_prefix=std::string(dir)+"/triangle_"+std::to_string(capture_counter.fetch_add(1));
        std::ofstream capture(capture_prefix+"_input.json");capture<<std::setprecision(17);
        capture<<"{\\"group\\":"<<group_id_<<",\\"boundary_attempt\\":"<<(boundary_attempt ? "true" : "false")
            <<",\\"point_budget\\":"<<point_budget<<",\\"options\\":\\""<<options<<"\\",\\"xy\\":[";
        for(index_t i=0;i<xy.size();++i) {if(i) capture<<",";capture<<xy[i];}
        capture<<"],\\"cells\\":[";
        for(index_t i=0;i<cells.size();++i) {if(i) capture<<",";capture<<cells[i];}
        capture<<"],\\"segments\\":[";
        for(index_t i=0;i<segments.size();++i) {if(i) capture<<",";capture<<segments[i];}
        capture<<"],\\"ids\\":[";
        for(index_t i=0;i<ids.size();++i) {if(i) capture<<",";capture<<ids[i];}
        capture<<"],\\"xyz\\":[";
        for(index_t i=0;i<xyz.size();++i) {if(i) capture<<",";capture<<"["<<xyz[i].x<<","<<xyz[i].y<<","<<xyz[i].z<<"]";}
        capture<<"]}";capture.close();
    }
    // Triangle初始化含共享全局常量，串行保护其调用；区域提取仍由Geogram并行执行。
    static std::mutex triangle_mutex;'''
assert code.count(old)==1;code=code.replace(old,new)
old='''        ::triangulate(options,&input,&output,nullptr);
    }
    auto release='''
new='''        ::triangulate(options,&input,&output,nullptr);
    }
    // 完成标记用于区分送入生成器后终止与后续接受判据，不能伪造未返回的数组。
    if(!capture_prefix.empty()) {
        std::ofstream capture(capture_prefix+"_returned.json");capture<<std::setprecision(17);
        capture<<"{\\"points\\":"<<output.numberofpoints<<",\\"triangles\\":"<<output.numberoftriangles<<",\\"xy\\":[";
        for(int i=0;i<2*output.numberofpoints;++i) {if(i) capture<<",";capture<<output.pointlist[i];}
        capture<<"]}";
    }
    auto release='''
assert code.count(old)==1;path.write_text(code.replace(old,new),'utf8')
driver=(here/'03-原生布尔质量与阶段计时.cpp').read_text('utf8')
driver=driver.replace('#include <string>','#include <string>\n// Linux诊断入口保留原终止现场，固定方法驱动不改变。\n#include <exception>\n#include <cstdlib>\n#include <execinfo.h>',1)
old='''    GEO::initialize(GEO::GEOGRAM_INSTALL_ALL);'''
new='''    GEO::initialize(GEO::GEOGRAM_INSTALL_ALL);
    // 只记录未处理异常和真实栈，随后退出诊断码，不返回或发布任何伪造网格。
    std::set_terminate([]() {
        std::cerr<<"NATIVE_DIAGNOSTIC_TERMINATE"<<std::endl;
        if(auto exception=std::current_exception()) {
            try {std::rethrow_exception(exception);}
            catch(const std::exception& error) {std::cerr<<"exception="<<error.what()<<std::endl;}
            catch(...) {std::cerr<<"exception=non_std"<<std::endl;}
        }
        void* frames[48];int count=backtrace(frames,48);backtrace_symbols_fd(frames,count,2);
        std::_Exit(201);
    });'''
assert driver.count(old)==1;(here/'468-旋转窄缝终止栈诊断原生入口.cpp').write_text(driver.replace(old,new),'utf8')
now=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
manifest=here/'462-旋转窄缝现场诊断源码清单.json'
manifest.write_text(json.dumps({'生成时间':now,'修改时间及修改内容':now+'，首次固定方法负例诊断副本',
 '文档概述':'不改固定已评价方法；仅捕获精确数组及未处理异常现场',
 '索引目录':['files'],'fixed_method_manifest_sha256':sha(here/'440-固定原生主候选方法封存清单.json'),
 'files':{name:sha(output/name) for name in names},'driver_sha256':sha(here/'468-旋转窄缝终止栈诊断原生入口.cpp')},ensure_ascii=False,indent=2)+'\n','utf8')
builder=(here/'371-共面重建前清理原生独立编译.py').read_text('utf8').replace('第二十轮','旋转窄缝诊断轮')
(here/'463-旋转窄缝现场诊断原生独立编译.py').write_text(builder,'utf8')
controller=(here/'372-共面重建前清理编译上传执行.py').read_text('utf8')
for a,b in [('20261006_21','20261007_24'),('第二十轮共面重建前合法新边清理',output.name),
 ('370-共面重建前合法新边清理源码清单.json',manifest.name),
 ('371-共面重建前清理原生独立编译.py','463-旋转窄缝现场诊断原生独立编译.py'),
 ('373-共面重建前清理实际编译执行记录.json','465-旋转窄缝现场诊断实际编译执行记录.json'),
 ('374-共面重建前清理实际编译控制台日志.txt','466-旋转窄缝现场诊断实际编译控制台日志.txt'),
 ('375-共面重建前清理实际原生编译记录.json','467-旋转窄缝现场诊断实际原生编译记录.json'),
 ('03-原生布尔质量与阶段计时.cpp','468-旋转窄缝终止栈诊断原生入口.cpp'),('第二十轮','旋转窄缝诊断轮')]:controller=controller.replace(a,b)
(here/'464-旋转窄缝现场诊断编译上传执行.py').write_text(controller,'utf8')
print('prepared_separate_termination_and_exact_triangle_input_capture')
