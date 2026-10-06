"""仅在新隔离诊断版本捕获实际Triangle输入与异常队列键，不改历史版本。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json

here=Path(__file__).resolve().parent
source=here/'第五轮共享子边同步生成'
output=here/'第六轮实际崩溃输入诊断源码';output.mkdir()
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
prior=json.loads((here/'68-第五轮共享子边同步源码清单.json').read_text('utf8'))
files={}
for name,digest in prior['files'].items():
    assert sha(source/name)==digest
    text=(source/name).read_text('utf8')
    if name=='mesh_surface_intersection_internal.cpp':
        text=text.replace('#include <mutex>','#include <mutex>\n#include <fstream>\n#include <iomanip>')
        old='''        std::lock_guard<std::mutex> guard(triangle_mutex);
        ::triangulate(options,&input,&output,nullptr);'''
        assert text.count(old)==1
        text=text.replace(old,'''        std::lock_guard<std::mutex> guard(triangle_mutex);
        // 仅在单独诊断开启时保存进入Triangle的实际数组，正式速度评价不开启。
        const char* capture=std::getenv("GEO_NATIVE_QUALITY_CAPTURE_DIR");
        if(capture!=nullptr) {
            std::ofstream dump(std::string(capture)+"/group_"+std::to_string(group_id_)+".json");
            dump << std::setprecision(17) << "{\\"group\\":" << group_id_ << ",\\"xy\\":[";
            for(index_t i=0;i<xy.size();++i) {if(i) dump << ",";dump << xy[i];}
            dump << "],\\"cells\\":[";
            for(index_t i=0;i<cells.size();++i) {if(i) dump << ",";dump << cells[i];}
            dump << "],\\"segments\\":[";
            for(index_t i=0;i<segments.size();++i) {if(i) dump << ",";dump << segments[i];}
            dump << "],\\"mesh_vertex_ids\\":[";
            for(index_t i=0;i<ids.size();++i) {if(i) dump << ",";dump << ids[i];}
            dump << "],\\"xyz\\":[";
            for(index_t i=0;i<xyz.size();++i) {
                if(i) dump << ",";
                dump << "[" << xyz[i].x << "," << xyz[i].y << "," << xyz[i].z << "]";
            }
            dump << "]}";dump.close();
        }
        ::triangulate(options,&input,&output,nullptr);''')
    p=output/name;p.write_text(text,'utf8')
    files['src/lib/geogram/mesh/'+name]=sha(p)
triangle=(here/'87-实际Triangle质量队列源码快照.c').read_text('utf8')
needle='  /* Determine the appropriate queue to put the bad triangle into.'
assert triangle.count(needle)==1
triangle=triangle.replace(needle,'''  /* 实际诊断仅捕获非法最短边平方长度，在原越界位置之前保存完整观测。 */
  if (!(badtri->key > 0.0) || badtri->key != badtri->key) {
    fprintf(stderr, "TRIANGLE_QUEUE_FAILURE {\\"key\\":%.17g,\\"vertices\\":[[%.17g,%.17g],[%.17g,%.17g],[%.17g,%.17g]]}\\n",
            badtri->key,badtri->triangorg[0],badtri->triangorg[1],
            badtri->triangdest[0],badtri->triangdest[1],badtri->triangapex[0],badtri->triangapex[1]);
    fflush(stderr);
    abort();
  }
'''+needle)
needle='  /* Are we inserting into an empty queue? */'
assert triangle.count(needle)==1
triangle=triangle.replace(needle,'''  /* 保存真实分桶越界，不把失败输入伪装成有效输出。 */
  if (queuenumber < 0 || queuenumber >= 4096) {
    fprintf(stderr,"TRIANGLE_QUEUE_RANGE_FAILURE key=%.17g queue=%d\\n",badtri->key,queuenumber);
    fflush(stderr);
    abort();
  }
'''+needle)
p=output/'triangle.c';p.write_text(triangle,'utf8');files['src/lib/geogram/third_party/triangle/triangle.c']=sha(p)
record={'生成时间':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),
        '修改时间及修改内容':'实际区域数组捕获及Triangle队列非法键诊断',
        '文档概述':'诊断版本不参与改进质量或速度结论；输入不合法时仍明确失败',
        '索引目录':['files'],'status':'prepared_actual_triangle_queue_diagnostic','files':files,
        'prior_manifest_sha256':sha(here/'68-第五轮共享子边同步源码清单.json')}
(here/'89-实际Triangle输入与队列诊断源码清单.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n','utf8')
builder=(here/'69-第五轮原生内核独立编译.py').read_text('utf8').replace('第五轮','第六轮诊断')
builder=builder.replace("shutil.copy2(root/'patch'/name,source/'src/lib/geogram/mesh'/name)","shutil.copy2(root/'patch'/name,source/name)")
(here/'90-实际崩溃捕获原生独立编译.py').write_text(builder,'utf8')
controller=(here/'70-第五轮隔离编译上传与执行.py').read_text('utf8')
for old,new in [('第五轮','第六轮诊断'),('20261006_06','20261006_07'),
                ('68-第六轮诊断共享子边同步源码清单.json','89-实际Triangle输入与队列诊断源码清单.json'),
                ('69-第六轮诊断原生内核独立编译.py','90-实际崩溃捕获原生独立编译.py'),
                ('71-第六轮诊断实际编译执行记录.json','92-实际崩溃捕获编译执行记录.json'),
                ('72-第六轮诊断实际编译控制台日志.txt','93-实际崩溃捕获编译控制台日志.txt'),
                ('73-第六轮诊断实际原生编译记录.json','94-实际崩溃捕获原生编译记录.json')]: controller=controller.replace(old,new)
old="source=here/'第六轮诊断共享子边同步生成'/name;assert sha(source)==digest;sftp.put(str(source),root+'/patch/'+name)"
assert controller.count(old)==1
controller=controller.replace(old,"source=here/'第六轮实际崩溃输入诊断源码'/Path(name).name;assert sha(source)==digest;sftp.put(str(source),root+'/patch/'+name)")
controller=controller.replace("with client.open_sftp() as sftp:\n        for name,digest",'''with client.open_sftp() as sftp:
        sftp.mkdir(root+'/patch/src');sftp.mkdir(root+'/patch/src/lib');sftp.mkdir(root+'/patch/src/lib/geogram')
        sftp.mkdir(root+'/patch/src/lib/geogram/mesh');sftp.mkdir(root+'/patch/src/lib/geogram/third_party')
        sftp.mkdir(root+'/patch/src/lib/geogram/third_party/triangle')
        for name,digest''')
(here/'91-实际崩溃捕获编译上传执行.py').write_text(controller,'utf8')
print('新隔离诊断源码已准备，未计改进成功')
