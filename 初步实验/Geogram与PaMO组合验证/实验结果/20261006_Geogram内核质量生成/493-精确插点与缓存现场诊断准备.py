"""保存真实共面插点及缓存对拍，不改变拓扑和谓词行为。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json
import hashlib
import shutil

here=Path(__file__).resolve().parent
folder=here/'精确插点与缓存现场诊断源码';folder.mkdir()
for p in (here/'精确谓词零扰动现场诊断源码').iterdir():
    if p.is_file():shutil.copy2(p,folder/p.name)
source=(folder/'mesh_surface_intersection_internal.cpp').read_text('utf8')
anchor='''        for(index_t v: vertices_) {
            if(keep_vertex_[v]) {
                ExactPoint P = I_.exact_vertex(v);
                v_idx_[v] = CDT.insert(exact::vec2h(P[u_], P[v_], P.w), v);
            } else {
                v_idx_[v] = NO_INDEX;
            }
        }

        // Insert constraints'''
assert source.count(anchor)==1
replacement='''        // 诊断插点逐行立即落盘，断言前的最后一个点也保留。
        std::ofstream trace;
        if(const char* directory=std::getenv("GEO_NATIVE_FAILURE_CAPTURE")) {
            static std::atomic<index_t> count(0);
            trace.open(std::string(directory)+"/cdt_insert_"+std::to_string(count++)+".jsonl");
            trace << std::setprecision(17);
            trace << "{\\\"u\\\":" << u_ << ",\\\"v\\\":" << v_ << ",\\\"facets\\\":[";
            for(index_t k=0;k<facets_.size();++k) {
                if(k) trace << ",";
                trace << facets_[k];
            }
            trace << "]}\\n";trace.flush();
        }
        auto dump_number=[&trace](const exact::scalar& value) {
            trace << "[";
            for(index_t k=0;k<value.length();++k) {
                if(k) trace << ",";
                trace << value.component(k);
            }
            trace << "]";
        };
        for(index_t v: vertices_) {
            if(keep_vertex_[v]) {
                ExactPoint P = I_.exact_vertex(v);
                if(trace.is_open()) {
                    trace << "{\\\"before_insert\\\":" << v << ",\\\"xyz\\\":[";
                    for(index_t k=0;k<3;++k) {
                        if(k) trace << ",";
                        dump_number(P[k]);
                    }
                    trace << "],\\\"w\\\":";dump_number(P.w);
                    trace << "}\\n";trace.flush();
                }
                v_idx_[v] = CDT.insert(exact::vec2h(P[u_], P[v_], P.w), v);
                if(trace.is_open()) {
                    trace << "{\\\"after_insert\\\":" << v << ",\\\"cdt_index\\\":" << v_idx_[v] << "}\\n";
                    trace.flush();
                }
            } else {
                v_idx_[v] = NO_INDEX;
            }
        }

        // Insert constraints'''
source=source.replace(anchor,replacement)
source=source.replace('''                CDT.insert_constraint(v1,v2,NO_INDEX);''','''                // 诊断约束前后的返回信息不改变原插入行为。
                if(trace.is_open()) {trace << "{\\\"constraint_before\\\":[" << v1 << "," << v2 << "]}\\n";trace.flush();}
                CDT.insert_constraint(v1,v2,NO_INDEX);
                if(trace.is_open()) {trace << "{\\\"constraint_after\\\":[" << v1 << "," << v2 << "]}\\n";trace.flush();}''')
source=source.replace('''        CDT.remove_external_triangles(true);
    }

// 此方法''','''        CDT.remove_external_triangles(true);
        if(trace.is_open()) {trace << "{\\\"completed\\\":true}\\n";trace.flush();}
    }

// 此方法''')
(folder/'mesh_surface_intersection_internal.cpp').write_text(source,'utf8')
cdt=(here/'492-实际精确CDT插点与缓存原始实现.cpp').read_text('utf8')
cdt=cdt.replace('#include <stack>','#include <stack>\n#include <cstdlib>\n#include <mutex>\n#include <cstdio>')
anchor='''        } else {
            result = it->second;
        }

        if(odd_order(i,j,k)) {'''
assert cdt.count(anchor)==1
cdt=cdt.replace(anchor,'''        } else {
            result = it->second;
            // 仅诊断副本对拍缓存，仍然返回原缓存结果。
            if(std::getenv("GEO_NATIVE_FAILURE_CAPTURE")) {
                Sign fresh=PCK::orient_2d(point_[K.indices[0]],point_[K.indices[1]],point_[K.indices[2]]);
                if(fresh != result) {
                    static std::mutex diagnostic_mutex;
                    std::lock_guard<std::mutex> guard(diagnostic_mutex);
                    std::fprintf(stderr,"CDT_CACHE_MISMATCH %u %u %u cached=%d fresh=%d\\n",
                        unsigned(K.indices[0]),unsigned(K.indices[1]),unsigned(K.indices[2]),int(result),int(fresh));
                }
            }
        }

        if(odd_order(i,j,k)) {''')
(folder/'CDT_2d.cpp').write_text(cdt,'utf8')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
manifest={'生成时间':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),
 '修改时间及修改内容':'首次精确插点及缓存现场诊断','文档概述':'仅记录，不发布和改变固定方法',
 '索引目录':['files'],'files':{p.name:sha(p) for p in folder.iterdir() if p.is_file()}}
(here/'494-精确插点缓存诊断源码清单.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n','utf8')
builder=(here/'480-精确谓词现场诊断独立编译.py').read_text('utf8').replace("'src/lib/geogram/numerics' if name == 'exact_geometry.cpp' else 'src/lib/geogram/mesh'","'src/lib/geogram/numerics' if name == 'exact_geometry.cpp' else ('src/lib/geogram/delaunay' if name == 'CDT_2d.cpp' else 'src/lib/geogram/mesh')")
(here/'495-精确插点缓存现场诊断编译.py').write_text(builder,'utf8')
controller=(here/'481-精确谓词现场诊断上传编译.py').read_text('utf8')
for old,new in [('20261007_25','20261007_26'),('479-精确谓词现场诊断源码清单','494-精确插点缓存诊断源码清单'),('精确谓词零扰动现场诊断源码','精确插点与缓存现场诊断源码'),('480-精确谓词现场诊断独立编译','495-精确插点缓存现场诊断编译'),('482-精确谓词现场诊断实际编译执行记录','497-精确插点缓存实际编译执行记录'),('483-精确谓词现场诊断实际编译控制台日志','498-精确插点缓存实际编译控制台日志'),('484-精确谓词现场诊断实际原生编译记录','499-精确插点缓存实际原生编译记录'),('精确谓词现场诊断轮_','精确插点缓存诊断轮_')]:controller=controller.replace(old,new)
(here/'496-精确插点缓存诊断上传编译.py').write_text(controller,'utf8')
worker=(here/'485-精确谓词全零现场隔离执行.py').read_text('utf8').replace('predicate_zero_capture_01','cdt_insert_capture_01')
(here/'500-精确插点缓存现场隔离执行.py').write_text(worker,'utf8')
controller=(here/'486-精确谓词全零现场执行取回.py').read_text('utf8')
for old,new in [('20261007_25','20261007_26'),('485-精确谓词全零现场隔离执行','500-精确插点缓存现场隔离执行'),('487-精确谓词全零现场实际执行取回记录','502-精确插点缓存现场实际执行取回记录'),('488-精确谓词全零现场实际控制台日志','503-精确插点缓存现场实际控制台日志'),('489-精确谓词全零现场全部输出','504-精确插点缓存现场全部输出'),('精确谓词全零现场全部输出','精确插点缓存现场全部输出'),('predicate_zero_capture_01','cdt_insert_capture_01')]:controller=controller.replace(old,new)
(here/'501-精确插点缓存现场执行取回.py').write_text(controller,'utf8')
print('prepared',len(manifest['files']))
