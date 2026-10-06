"""保留第七轮，覆盖内部点无法改善的差面，并保留已成功内部改善作为回退。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json

here=Path(__file__).resolve().parent
source=here/'第七轮内部点优先与共边邻域重生成'
output=here/'第八轮差面边界触发与内部改善保留';output.mkdir()
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
prior=json.loads((here/'110-有界共边与邻域再生成源码清单.json').read_text('utf8'))
for name,digest in prior['files'].items():
    assert sha(source/name)==digest
    (output/name).write_bytes((source/name).read_bytes())
path=output/'mesh_surface_intersection_internal.cpp';text=path.read_text('utf8')
old='''    // 点数改善但坏面面积上升时，再试一次有界边界细化，不能放松原质量判定。
    if(!valid && allow_boundary && !boundary_attempt && after_score_computed &&
       after.bad<before.bad && after.area>before.area) {'''
new='''    // 内部点未能改善的有效差面也允许一次有界边界细化，不能放松最终质量判定。
    if(!valid && allow_boundary && !boundary_attempt && after_score_computed && after.valid && after.bad>0) {'''
assert text.count(old)==1;text=text.replace(old,new);path.write_text(text,'utf8')
path=output/'mesh_surface_intersection.cpp';text=path.read_text('utf8')
old='''            reference.insert(reference.end(),region.reference_triangles.begin(),region.reference_triangles.end());
            vector<index_t> ids;'''
assert text.count(old)==1;text=text.replace(old,'            vector<index_t> ids;')
old='''            for(index_t i=0;i<region.boundary_edges.size();++i) {
                if(region.boundary_edges[i].first!=NO_INDEX) {'''
new='''            bool modifies_boundary=false;
            for(const auto& edge:region.boundary_edges) modifies_boundary=modifies_boundary || edge.first!=NO_INDEX;
            // 共边试验失败时保留其他区域已成功的内部点改善，不退回更差的官方CDT。
            if(modifies_boundary) {
                reference.insert(reference.end(),region.reference_triangles.begin(),region.reference_triangles.end());
            } else {
                for(index_t v:region.triangles) reference.push_back(v<original_vertices ? v : ids[v-original_vertices]);
            }
            for(index_t i=0;i<region.boundary_edges.size();++i) {
                if(region.boundary_edges[i].first!=NO_INDEX) {'''
assert text.count(old)==1;text=text.replace(old,new)
text=text.replace('// 保存原版CDT同区域结果，整体检查失败时回到这份准确生成结果。',
                  '// 保存准确CDT作为边界方案回退；未改边界的内部改善随后进入整体参照。')
text=text.replace('// 所有参照编号仍有效；整体失败时删除全部暂定面并恢复完整原版CDT列表。',
                  '// 所有参照编号仍有效；整体失败时恢复保留内部改善的完整参照列表。')
path.write_text(text,'utf8')
record={'生成时间':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),
        '修改时间及修改内容':'边界触发覆盖未改善差面；整体回退保留无边界内部改善',
        '文档概述':'第八轮原生候选，原第七轮源码和结果冻结保留',
        '索引目录':['files'],'status':'prepared_eighth_bounded_boundary_trigger_and_internal_fallback',
        'files':{p.name:sha(p) for p in output.iterdir()},'prior_manifest_sha256':sha(here/'110-有界共边与邻域再生成源码清单.json'),
        'internal_point_budget':64,'boundary_attempt_budget':128,'neighbor_internal_budget':128,'neighbor_passes_max':1}
(here/'125-差面边界触发与内部改善保留源码清单.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n','utf8')
builder=(here/'111-有界邻域生成原生独立编译.py').read_text('utf8').replace('第七轮','第八轮')
(here/'126-内部改善保留原生独立编译.py').write_text(builder,'utf8')
controller=(here/'112-有界邻域生成隔离编译上传执行.py').read_text('utf8')
for old,new in [('第七轮','第八轮'),('20261006_08','20261006_09'),
                ('110-有界共边与邻域再生成源码清单.json','125-差面边界触发与内部改善保留源码清单.json'),
                ('第八轮内部点优先与共边邻域重生成','第八轮差面边界触发与内部改善保留'),
                ('111-有界邻域生成原生独立编译.py','126-内部改善保留原生独立编译.py'),
                ('113-有界邻域生成实际编译执行记录.json','128-内部改善保留实际编译执行记录.json'),
                ('114-有界邻域生成实际编译控制台日志.txt','129-内部改善保留实际编译控制台日志.txt'),
                ('115-有界邻域生成实际原生编译记录.json','130-内部改善保留实际原生编译记录.json')]:controller=controller.replace(old,new)
(here/'127-内部改善保留原生编译上传执行.py').write_text(controller,'utf8')
print('差面边界触发与内部改善保留源码已准备')
