"""新开发版本拒绝带机器尺度新边的不合格共边候选，旧固定评价保持不变。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json
import shutil

here=Path(__file__).resolve().parent
folder=here/'第二十二轮递归前机器新边拒绝';folder.mkdir()
for name in ['mesh_surface_intersection.cpp','mesh_surface_intersection_internal.cpp','mesh_surface_intersection_internal.h']:
    shutil.copy2(here/'共面前清理固定原生候选封存'/name,folder/name)
p=folder/'mesh_surface_intersection.cpp';source=p.read_text('utf8')
anchor='''        bool rebuilt_shared_neighbors=false;
        if(!shared_splits.empty() && allow_boundary_generation && !quality_is_acceptable(candidate_score)) {'''
assert source.count(anchor)==1
replacement='''        bool rebuilt_shared_neighbors=false;
        // 整体已经不合格且含机器尺度新边时撤回共边方案，禁止向准确CDT提交不可分辨的新边。
        bool unresolved_new_edge=false;
        if(!shared_splits.empty() && allow_boundary_generation && !quality_is_acceptable(candidate_score)) {
            for(index_t f:mesh_.facets) if(!remove_f[f]) {
                for(index_t k=0;k<3;++k) {
                    index_t a=mesh_.facets.vertex(f,k),b=mesh_.facets.vertex(f,(k+1)%3);
                    if(a<original_vertices && b<original_vertices) continue;
                    const vec3& p=mesh_.vertices.point(a);const vec3& q=mesh_.vertices.point(b);
                    double scale=std::max({std::abs(p.x),std::abs(p.y),std::abs(p.z),std::abs(q.x),std::abs(q.y),std::abs(q.z)});
                    unresolved_new_edge=unresolved_new_edge || length(p-q)<=128.0*std::numeric_limits<double>::epsilon()*scale;
                }
            }
        }
        // 沿用整体拒绝后的参照恢复，不改变原顶点、不放宽质量判据，也不修改精确谓词。
        if(!shared_splits.empty() && allow_boundary_generation && !quality_is_acceptable(candidate_score) && !unresolved_new_edge) {'''
source=source.replace(anchor,replacement)
p.write_text(source,'utf8')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
manifest={'生成时间':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),
 '修改时间及修改内容':'首次新边不可分辨时拒绝不合格共边方案',
 '文档概述':'评价后新开发版；旧固定方法和16例评价身份保留；未称解决一般CDT故障',
 '索引目录':['files'],'files':{p.name:sha(p) for p in folder.iterdir() if p.is_file()}}
(here/'508-递归前机器新边拒绝版本源码清单.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n','utf8')
(here/'509-递归前机器新边拒绝原生独立编译.py').write_text((here/'463-旋转窄缝现场诊断原生独立编译.py').read_text('utf8'),'utf8')
controller=(here/'464-旋转窄缝现场诊断编译上传执行.py').read_text('utf8')
for old,new in [('20261007_24','20261007_27'),('462-旋转窄缝现场诊断源码清单','508-递归前机器新边拒绝版本源码清单'),('旋转窄缝原生终止现场诊断源码','第二十二轮递归前机器新边拒绝'),('463-旋转窄缝现场诊断原生独立编译','509-递归前机器新边拒绝原生独立编译'),('468-旋转窄缝终止栈诊断原生入口','03-原生布尔质量与阶段计时'),('465-旋转窄缝现场诊断实际编译执行记录','511-递归前机器新边拒绝实际编译执行记录'),('466-旋转窄缝现场诊断实际编译控制台日志','512-递归前机器新边拒绝实际编译控制台日志'),('467-旋转窄缝现场诊断实际原生编译记录','513-递归前机器新边拒绝实际原生编译记录'),('旋转窄缝诊断轮_','递归前机器新边拒绝_')]:controller=controller.replace(old,new)
(here/'510-递归前机器新边拒绝上传编译.py').write_text(controller,'utf8')
print('prepared',len(manifest['files']))
