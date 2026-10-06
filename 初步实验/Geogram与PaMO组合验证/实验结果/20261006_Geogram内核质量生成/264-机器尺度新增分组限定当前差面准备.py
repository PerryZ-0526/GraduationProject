"""新增近共面分组只服务当前布尔差面，官方准确共面路径保持。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json

here=Path(__file__).resolve().parent
source=here/'第十五轮共边受影响区域限定再生成'
output=here/'第十六轮当前差面触发近共面分组';output.mkdir()
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
prior_path=here/'241-共边受影响区域限定再生成源码清单.json'
prior=json.loads(prior_path.read_text('utf8'))
for name,digest in prior['files'].items():
    assert sha(source/name)==digest
    (output/name).write_bytes((source/name).read_bytes())
path=output/'mesh_surface_intersection_internal.h';code=path.read_text('utf8')
old='''	    const vec3& q1, const vec3& q2, const vec3& q3
	) const;'''
new='''	    const vec3& q1, const vec3& q2, const vec3& q3,
            // 仅新增机器尺度合并受质量触发控制，原准确共面判据不改变。
            bool allow_machine = true
	) const;'''
assert code.count(old)==1;path.write_text(code.replace(old,new),'utf8')
path=output/'mesh_surface_intersection_internal.cpp';code=path.read_text('utf8')
old='''        parallel_for(
            0, mesh_.facet_corners.nb(),'''
new='''        // 当前布尔网格的差面一次计算；按面独立写整数，避免并行位容器写冲突。
        vector<index_t> current_bad(mesh_.facets.nb(),0);
        parallel_for(0,mesh_.facets.nb(),[&](index_t f) {
            const vec3 p[3]={mesh_.vertices.point(mesh_.facets.vertex(f,0)),
                mesh_.vertices.point(mesh_.facets.vertex(f,1)),mesh_.vertices.point(mesh_.facets.vertex(f,2))};
            for(index_t k=0;k<3;++k) {
                vec3 a=p[(k+1)%3]-p[k],b=p[(k+2)%3]-p[k];
                if(std::atan2(length(cross(a,b)),dot(a,b))*180.0/M_PI<10.0) {current_bad[f]=1;break;}
            }
        });

        parallel_for(
            0, mesh_.facet_corners.nb(),'''
assert code.count(old)==1;code=code.replace(old,new)
old='''		if(triangles_are_coplanar(p1,p2,p3,q1,q2,q3)) {'''
new='''                // 新合并只为当前产生的差面服务，不能仅凭原输入面好坏跳过切口差面。
		if(triangles_are_coplanar(p1,p2,p3,q1,q2,q3,current_bad[f1] || current_bad[f2])) {'''
assert code.count(old)==1;code=code.replace(old,new)
old='''	const vec3& q1, const vec3& q2, const vec3& q3
    ) const {'''
new='''	const vec3& q1, const vec3& q2, const vec3& q3,
        bool allow_machine
    ) const {'''
assert code.count(old)==1;code=code.replace(old,new)
old='''            // 保存坐标造成的机器尺度非共面可单独核对；真实曲率和厚度不依靠角度容差合并。'''
new='''            // 当前两面都没有差面时，保持原版不合并，减少无收益的新增区域。
            if(!allow_machine) return false;
            // 保存坐标造成的机器尺度非共面可单独核对；真实曲率和厚度不依靠角度容差合并。'''
assert code.count(old)==1;path.write_text(code.replace(old,new),'utf8')
now=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
manifest=here/'265-当前差面触发近共面分组源码清单.json'
manifest.write_text(json.dumps({'生成时间':now,'修改时间及修改内容':now+'，首次限定无准确共面新增分组到当前差面',
 '文档概述':'不按原输入面好坏过滤新切口；准确共面、条带及完整接受判据保持',
 '索引目录':['files','changes'],'prior_manifest_sha256':sha(prior_path),
 'files':{name:sha(output/name) for name in prior['files']},
 'changes':['当前布尔面质量一次并行计算','新增机器尺度合并须涉及当前差面','原准确共面路径不变']},ensure_ascii=False,indent=2)+'\n','utf8')
builder=(here/'242-受影响区域限定再生成原生独立编译.py').read_text('utf8').replace('第十五轮','第十六轮')
(here/'266-当前差面触发分组原生独立编译.py').write_text(builder,'utf8')
controller=(here/'243-受影响区域限定再生成编译上传执行.py').read_text('utf8')
for a,b in [('20261006_16','20261006_17'),('第十五轮共边受影响区域限定再生成',output.name),
 ('241-共边受影响区域限定再生成源码清单.json',manifest.name),
 ('242-受影响区域限定再生成原生独立编译.py','266-当前差面触发分组原生独立编译.py'),
 ('244-受影响区域限定实际编译执行记录.json','268-当前差面分组实际编译执行记录.json'),
 ('245-受影响区域限定实际编译控制台日志.txt','269-当前差面分组实际编译控制台日志.txt'),
 ('246-受影响区域限定实际原生编译记录.json','270-当前差面分组实际原生编译记录.json'),
 ('第十五轮','第十六轮')]:controller=controller.replace(a,b)
(here/'267-当前差面触发分组编译上传执行.py').write_text(controller,'utf8')
print('prepared_current_boolean_quality_trigger_for_machine_scale_grouping')
