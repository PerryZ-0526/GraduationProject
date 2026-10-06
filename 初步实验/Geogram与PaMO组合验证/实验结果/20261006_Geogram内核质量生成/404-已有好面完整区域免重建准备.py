"""保留现有好面完整组，减少没有质量收益的准确CDT；共边受影响组仍完整处理。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json

here=Path(__file__).resolve().parent
source=here/'第二十轮共面重建前合法新边清理'
output=here/'第二十一轮已有好面完整区域免重建';output.mkdir()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
prior_path=here/'370-共面重建前合法新边清理源码清单.json'
prior=json.loads(prior_path.read_text('utf8'))
for name,digest in prior['files'].items():
    assert sha(source/name)==digest
    (output/name).write_bytes((source/name).read_bytes())
path=output/'mesh_surface_intersection.cpp';code=path.read_text('utf8')
old='''        for(index_t f:mesh_.facets) if(quality_shared_active[f]) active_groups[facet_group[f]]=true;

        // 并行阶段只读取共享网格，区域内部点及面暂存在各自的结果中。'''
new='''        for(index_t f:mesh_.facets) if(quality_shared_active[f]) active_groups[facet_group[f]]=true;
        // 当前布尔区域已经全为好面且没有共边改动时保留原面，不仅凭初始输入质量判断。
        vector<bool> group_needs_quality(nb_groups,false);
        for(index_t f:mesh_.facets) {
            index_t group=facet_group[f];
            if(group_needs_quality[group]) continue;
            vec3 p[3]={mesh_.vertices.point(mesh_.facets.vertex(f,0)),
                mesh_.vertices.point(mesh_.facets.vertex(f,1)),mesh_.vertices.point(mesh_.facets.vertex(f,2))};
            double area=length(cross(p[1]-p[0],p[2]-p[0]));
            if(!std::isfinite(area) || area<=0.0) {group_needs_quality[group]=true;continue;}
            for(index_t k=0;k<3;++k) {
                vec3 a=p[(k+1)%3]-p[k],b=p[(k+2)%3]-p[k];
                double angle=std::atan2(length(cross(a,b)),dot(a,b))*180.0/M_PI;
                if(!std::isfinite(angle) || angle<10.0) {group_needs_quality[group]=true;break;}
            }
        }

        // 并行阶段只读取共享网格，区域内部点及面暂存在各自的结果中。'''
assert code.count(old)==1;code=code.replace(old,new)
old='''                    // 初次生成仍覆盖所有组，二次仅处理共边改动实际涉及的完整组。
                    if(!allow_boundary_generation && !active_groups[group]) continue;
                    coplanar.get(group_facet[group],group);'''
new='''                    // 含差面的完整组才重建；共边实际改动组仍处理，保留接缝锚点和后续质量检查。
                    if(!allow_boundary_generation && !active_groups[group]) continue;
                    if(!group_needs_quality[group] && !active_groups[group]) continue;
                    coplanar.get(group_facet[group],group);'''
assert code.count(old)==1;path.write_text(code.replace(old,new),'utf8')
now=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
manifest=here/'405-已有好面完整区域免重建源码清单.json'
manifest.write_text(json.dumps({'生成时间':now,'修改时间及修改内容':now+'，跳过已好且无共边改变的完整组',
 '文档概述':'分组不改；当前差面判断；保留受影响再生成、完整质量与新边约束',
 '索引目录':['files','changes'],'prior_manifest_sha256':sha(prior_path),
 'files':{name:sha(output/name) for name in prior['files']},
 'changes':['当前区域是否有小角或非法面积','仅零差面且无共边改动组保持原面','其余完整区域及最终检查保持']},ensure_ascii=False,indent=2)+'\n','utf8')
builder=(here/'371-共面重建前清理原生独立编译.py').read_text('utf8').replace('第二十轮','第二十一轮')
(here/'406-好面区域免重建原生独立编译.py').write_text(builder,'utf8')
controller=(here/'372-共面重建前清理编译上传执行.py').read_text('utf8')
for a,b in [('20261006_21','20261007_22'),(source.name,output.name),
 ('370-共面重建前合法新边清理源码清单.json',manifest.name),
 ('371-共面重建前清理原生独立编译.py','406-好面区域免重建原生独立编译.py'),
 ('373-共面重建前清理实际编译执行记录.json','408-好面区域免重建实际编译执行记录.json'),
 ('374-共面重建前清理实际编译控制台日志.txt','409-好面区域免重建实际编译控制台日志.txt'),
 ('375-共面重建前清理实际原生编译记录.json','410-好面区域免重建实际原生编译记录.json'),
 ('第二十轮','第二十一轮')]:controller=controller.replace(a,b)
(here/'407-好面区域免重建编译上传执行.py').write_text(controller,'utf8')
print('prepared_zero_bad_unchanged_group_preservation')
