"""仅增加精确谓词现场保存；固定方法和原始评价保持不变。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json
import shutil

here=Path(__file__).resolve().parent
folder=here/'精确谓词零扰动现场诊断源码'
folder.mkdir()
prior=here/'旋转窄缝原生终止现场诊断源码'
for source in prior.iterdir():
    if source.is_file(): shutil.copy2(source,folder/source.name)
source=(here/'477-实际精确圆谓词原始实现.cpp').read_text('utf8')
source=source.replace('#include <geogram/basic/logger.h>','#include <geogram/basic/logger.h>\n#include <cstdlib>\n#include <fstream>\n#include <iomanip>\n#include <mutex>')
start=source.index('Sign incircle_2d_SOS_with_lengths(')
anchor='''            return SOS(
                vec2HgLexicoCompare<expansion_nt>(),
                p0, SOS_result( det3_111_sign(p1,p2,p3)),
                p1, SOS_result(-det3_111_sign(p0,p2,p3)),
                p2, SOS_result( det3_111_sign(p0,p1,p3)),
                p3, SOS_result(-det3_111_sign(p0,p1,p2))
            );'''
at=source.index(anchor,start)
probe='''            // 仅诊断副本在四个扰动项全零时保存原始展开项，不改变谓词返回。
            if(const char* directory = std::getenv("GEO_NATIVE_FAILURE_CAPTURE")) {
                int s0 = int(det3_111_sign(p1,p2,p3));
                int s1 = -int(det3_111_sign(p0,p2,p3));
                int s2 = int(det3_111_sign(p0,p1,p3));
                int s3 = -int(det3_111_sign(p0,p1,p2));
                if(s0 == 0 && s1 == 0 && s2 == 0 && s3 == 0) {
                    static std::mutex diagnostic_mutex;
                    std::lock_guard<std::mutex> guard(diagnostic_mutex);
                    std::ofstream output(std::string(directory)+"/predicate_zero_terms.json");
                    output << std::setprecision(17);
                    auto dump_number = [&output](const expansion_nt& number) {
                        output << "[";
                        for(index_t k=0;k<number.length();++k) {
                            if(k != 0) output << ",";
                            output << number.component(k);
                        }
                        output << "]";
                    };
                    const vec2HE* points[4] = {&p0,&p1,&p2,&p3};
                    double lengths[4] = {l0,l1,l2,l3};
                    output << "{\\\"points\\\":[";
                    for(index_t k=0;k<4;++k) {
                        if(k != 0) output << ",";
                        output << "{\\\"x\\\":"; dump_number(points[k]->x);
                        output << ",\\\"y\\\":"; dump_number(points[k]->y);
                        output << ",\\\"w\\\":"; dump_number(points[k]->w);
                        output << ",\\\"length\\\":" << lengths[k] << "}";
                    }
                    output << "],\\\"sos_terms\\\":[0,0,0,0]}\\n";
                    output.close();
                }
            }
'''
source=source[:at]+probe+source[at:]
(folder/'exact_geometry.cpp').write_text(source,'utf8')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
manifest={'生成时间':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),
 '修改时间及修改内容':'首次精确谓词全零现场记录副本','文档概述':'仅记录四个真实点展开项，不修改精确谓词或已封存方法',
 '索引目录':['files'],'files':{p.name:sha(p) for p in folder.iterdir() if p.is_file()}}
(here/'479-精确谓词现场诊断源码清单.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n','utf8')
builder=(here/'463-旋转窄缝现场诊断原生独立编译.py').read_text('utf8')
builder=builder.replace("source/'src/lib/geogram/mesh'/name","source/('src/lib/geogram/numerics' if name == 'exact_geometry.cpp' else 'src/lib/geogram/mesh')/name")
(here/'480-精确谓词现场诊断独立编译.py').write_text(builder,'utf8')
controller=(here/'464-旋转窄缝现场诊断编译上传执行.py').read_text('utf8')
for old,new in [('20261007_24','20261007_25'),('462-旋转窄缝现场诊断源码清单','479-精确谓词现场诊断源码清单'),('旋转窄缝原生终止现场诊断源码','精确谓词零扰动现场诊断源码'),('463-旋转窄缝现场诊断原生独立编译','480-精确谓词现场诊断独立编译'),('465-旋转窄缝现场诊断实际编译执行记录','482-精确谓词现场诊断实际编译执行记录'),('466-旋转窄缝现场诊断实际编译控制台日志','483-精确谓词现场诊断实际编译控制台日志'),('467-旋转窄缝现场诊断实际原生编译记录','484-精确谓词现场诊断实际原生编译记录'),('旋转窄缝诊断轮_','精确谓词现场诊断轮_')]:
    controller=controller.replace(old,new)
(here/'481-精确谓词现场诊断上传编译.py').write_text(controller,'utf8')
worker=(here/'469-旋转窄缝终止现场隔离执行.py').read_text('utf8').replace('rotated_gap_failure_capture_01','predicate_zero_capture_01')
(here/'485-精确谓词全零现场隔离执行.py').write_text(worker,'utf8')
controller=(here/'470-旋转窄缝终止现场上传执行取回.py').read_text('utf8')
for old,new in [('20261007_24','20261007_25'),('469-旋转窄缝终止现场隔离执行','485-精确谓词全零现场隔离执行'),('471-旋转窄缝终止现场实际执行取回记录','487-精确谓词全零现场实际执行取回记录'),('472-旋转窄缝终止现场实际控制台日志','488-精确谓词全零现场实际控制台日志'),('473-旋转窄缝原生终止现场全部输出','489-精确谓词全零现场全部输出'),('旋转窄缝原生终止现场全部输出','精确谓词全零现场全部输出'),('rotated_gap_failure_capture_01','predicate_zero_capture_01')]:
    controller=controller.replace(old,new)
(here/'486-精确谓词全零现场执行取回.py').write_text(controller,'utf8')
print('prepared',len(manifest['files']))
