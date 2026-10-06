"""先保存旧缺口观测，再单独保留好区顶点测试免重建；旧封存不改。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json
import shutil
import numpy as np
import trimesh

here=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
old=here/'好面免重建原生CT十六刀全部实际输出/e00_candidate.obj'
mesh=trimesh.load(old,process=False,force='mesh')
edges,counts=np.unique(np.sort(mesh.edges,axis=1),axis=0,return_counts=True)
boundary=edges[counts==1];vertices=np.unique(boundary);observations=[]
for a,b in boundary:
    p,q=mesh.vertices[[a,b]];d=q-p;den=float(d@d)
    if den==0:continue
    for v in vertices:
        if v in [a,b]:continue
        t=float((mesh.vertices[v]-p)@d)/den
        if not 0<t<1:continue
        distance=float(np.linalg.norm(mesh.vertices[v]-(p+t*d)))
        bound=128*np.finfo(float).eps*np.max(np.abs(mesh.vertices[[a,b,v]]))
        if distance<=bound:
            observations.append({'edge_vertices':[int(a),int(b)],'interior_boundary_vertex':int(v),
                'parameter':t,'point_to_edge_distance_mm':distance,'machine_scale_bound_mm':float(bound)})
now=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
diagnosis={'生成时间':now,'修改时间及修改内容':'首次旧好区免重建保存结果接缝诊断',
 '文档概述':'浮点保存对象的接缝观测支持边界锚点假设，不替代一般精确因果证明',
 '索引目录':['observations'],'status':'completed_saved_boundary_endpoint_inside_edge_observation',
 'source_sha256':sha(old),'boundary_edges':len(boundary),'observations':observations,
 'exact_certificate':False,'hypothesis':'保留好区原面后，邻侧共面重建删除其共线边界顶点，产生T型接缝'}
(here/'589-旧好区免重建接缝缺口只读诊断.json').write_text(json.dumps(diagnosis,ensure_ascii=False,indent=2)+'\n','utf8')
folder=here/'第二十三轮保留好区顶点免重建';folder.mkdir()
prior=json.loads((here/'569-新边拒绝原生主候选完整开发终态封存清单.json').read_text('utf8'))
for name in ['mesh_surface_intersection.cpp','mesh_surface_intersection_internal.cpp','mesh_surface_intersection_internal.h']:
    source=here/'新边拒绝固定原生候选封存'/name;assert sha(source)==prior['files'][name]
    shutil.copy2(source,folder/name)
path=folder/'mesh_surface_intersection.cpp';source=path.read_text('utf8')
old_source=(here/'第二十一轮已有好面完整区域免重建/mesh_surface_intersection.cpp').read_text('utf8')
start=old_source.index('        // 当前布尔区域已经全为好面')
end=old_source.index('        // 并行阶段只读取共享网格',start)
quality_block=old_source[start:end]
anchor='''        // 并行阶段只读取共享网格，区域内部点及面暂存在各自的结果中。'''
assert source.count(anchor)==1
keep_block='''        // 保留完整好区原面时，它的每个原顶点均为接缝锚点，邻区准确CDT不可删除。
        for(index_t f:mesh_.facets) {
            index_t group=facet_group[f];
            if(group_needs_quality[group] || active_groups[group]) continue;
            for(index_t k=0;k<3;++k) keep_vertex[mesh_.facets.vertex(f,k)]=true;
        }

'''
source=source.replace(anchor,quality_block+keep_block+anchor)
anchor='''                    // 初次生成仍覆盖所有组，二次仅处理共边改动实际涉及的完整组。
                    if(!allow_boundary_generation && !active_groups[group]) continue;'''
assert source.count(anchor)==1
source=source.replace(anchor,'''                    // 差面组及共边活动组完整重建，其余好组原面保持且所有原顶点已固定保留。
                    if(!allow_boundary_generation && !active_groups[group]) continue;
                    if(!group_needs_quality[group] && !active_groups[group]) continue;''')
path.write_text(source,'utf8')
manifest={'生成时间':now,'修改时间及修改内容':'首次保留好区全部原顶点的免重建开发版',
 '文档概述':'单一免重建及接缝顶点机制；当前封存569号和独立评价不改；尚未编译或验证',
 '索引目录':['files'],'prior_method_sha256':sha(here/'569-新边拒绝原生主候选完整开发终态封存清单.json'),
 'files':{p.name:sha(p) for p in folder.iterdir() if p.is_file()}}
(here/'590-保留好区顶点免重建源码清单.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n','utf8')
builder=(here/'509-递归前机器新边拒绝原生独立编译.py').read_text('utf8')
builder=builder.replace('首次旋转窄缝诊断轮内部零位移版本实际编译','首次保留好区顶点免重建版本实际编译')
(here/'591-保留好区顶点免重建原生独立编译.py').write_text(builder,'utf8')
controller=(here/'510-递归前机器新边拒绝上传编译.py').read_text('utf8')
for old,new in [('20261007_27','20261007_30'),('508-递归前机器新边拒绝版本源码清单','590-保留好区顶点免重建源码清单'),('第二十二轮递归前机器新边拒绝','第二十三轮保留好区顶点免重建'),('509-递归前机器新边拒绝原生独立编译','591-保留好区顶点免重建原生独立编译'),('511-递归前机器新边拒绝实际编译执行记录','593-保留好区顶点免重建实际编译执行记录'),('512-递归前机器新边拒绝实际编译控制台日志','594-保留好区顶点免重建实际编译控制台日志'),('513-递归前机器新边拒绝实际原生编译记录','595-保留好区顶点免重建实际原生编译记录'),('递归前机器新边拒绝_','保留好区顶点免重建_')]:
    controller=controller.replace(old,new)
(here/'592-保留好区顶点免重建上传编译.py').write_text(controller,'utf8')
print('prepared',len(observations),'saved_seam_observations')
