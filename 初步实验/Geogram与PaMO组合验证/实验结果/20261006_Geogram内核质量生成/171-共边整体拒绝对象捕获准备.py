"""在新诊断副本捕获整体判定前网格，不能将未通过对象作为交付结果。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json

here=Path(__file__).resolve().parent
source=here/'第十轮种子分组与边界一致生成'
output=here/'第十一轮整体拒绝前网格诊断';output.mkdir()
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
prior_path=here/'154-种子分组与边界一致生成源码清单.json'
prior=json.loads(prior_path.read_text('utf8'))
for name,digest in prior['files'].items():
    assert sha(source/name)==digest
    (output/name).write_bytes((source/name).read_bytes())
path=output/'mesh_surface_intersection.cpp';code=path.read_text('utf8')
code=code.replace('#include <sstream>', '#include <sstream>\n// 诊断副本以完整双精度保存未接受对象，不改变生成与接受判据。\n#include <fstream>\n#include <iomanip>')
anchor='''        NativeQualityScore baseline_score=native_quality_score(mesh_,reference);'''
capture='''        // 仅显式诊断变量开启时保存整体判定前对象，不计为正式结果或速度样本。
        if(const char* prefix=std::getenv("GEO_NATIVE_QUALITY_PROPOSAL_PREFIX")) {
            std::string base=std::string(prefix)+"_depth"+std::to_string(quality_neighbor_depth);
            std::ofstream out(base+".obj");out << std::setprecision(17);
            for(index_t v:mesh_.vertices) {
                const vec3& p=mesh_.vertices.point(v);out << "v " << p.x << ' ' << p.y << ' ' << p.z << '\\n';
            }
            for(index_t f:mesh_.facets) if(!remove_f[f]) {
                out << "f " << mesh_.facets.vertex(f,0)+1 << ' ' << mesh_.facets.vertex(f,1)+1 << ' ' << mesh_.facets.vertex(f,2)+1 << '\\n';
            }
            std::ofstream edges(base+"_splits.txt");edges << std::setprecision(17);
            for(const auto& request:shared_splits) {
                index_t a=request.first.first,b=request.first.second;
                const vec3 delta=mesh_.vertices.point(b)-mesh_.vertices.point(a);
                coord_index_t axis=0;
                for(coord_index_t k=1;k<3;++k) if(std::abs(delta[k])>std::abs(delta[axis])) axis=k;
                edges << a << ' ' << b;
                for(index_t v:request.second) edges << ' ' << v << ':' << (mesh_.vertices.point(v)[axis]-mesh_.vertices.point(a)[axis])/delta[axis];
                edges << '\\n';
            }
        }
'''
assert code.count(anchor)==1
path.write_text(code.replace(anchor,capture+anchor),'utf8')
now=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
manifest=here/'172-整体拒绝对象捕获源码清单.json'
manifest.write_text(json.dumps({'生成时间':now,'修改时间及修改内容':now+'，首次新增可关闭的拒绝前对象捕获',
    '文档概述':'质量判据及算法不改；仅分析共边合并为何造成新的差面','索引目录':['files'],
    'prior_manifest_sha256':sha(prior_path),'files':{name:sha(output/name) for name in prior['files']}},ensure_ascii=False,indent=2)+'\n','utf8')
builder=(here/'155-种子分组与边界一致原生独立编译.py').read_text('utf8').replace('第十轮','第十一轮诊断')
(here/'173-整体拒绝对象捕获原生独立编译.py').write_text(builder,'utf8')
controller=(here/'156-种子分组与边界一致编译上传执行.py').read_text('utf8')
for a,b in [('20261006_11','20261006_12'),('第十轮种子分组与边界一致生成',output.name),
            ('154-种子分组与边界一致生成源码清单.json',manifest.name),
            ('155-种子分组与边界一致原生独立编译.py','173-整体拒绝对象捕获原生独立编译.py'),
            ('157-种子分组与边界一致实际编译执行记录.json','175-整体拒绝捕获实际编译执行记录.json'),
            ('158-种子分组与边界一致实际编译控制台日志.txt','176-整体拒绝捕获实际编译控制台日志.txt'),
            ('159-种子分组与边界一致实际原生编译记录.json','177-整体拒绝捕获实际原生编译记录.json'),
            ('第十轮','第十一轮诊断')]:controller=controller.replace(a,b)
(here/'174-整体拒绝对象捕获编译上传执行.py').write_text(controller,'utf8')
print('prepared_proposal_capture_without_acceptance_changes')
