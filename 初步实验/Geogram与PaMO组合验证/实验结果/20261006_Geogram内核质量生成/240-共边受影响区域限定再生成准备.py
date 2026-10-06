"""只对共边实际受影响组作第二次生成，原质量检查与回退仍覆盖全网格。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json

here=Path(__file__).resolve().parent
source=here/'第十四轮共边邻接索引成本修订'
output=here/'第十五轮共边受影响区域限定再生成';output.mkdir()
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
prior_path=here/'224-共边邻接索引成本修订源码清单.json'
prior=json.loads(prior_path.read_text('utf8'))
for name,digest in prior['files'].items():
    assert sha(source/name)==digest
    (output/name).write_bytes((source/name).read_bytes())
path=output/'mesh_surface_intersection.cpp';code=path.read_text('utf8')
old='''    remove_f.resize(M.facets.nb(),0);
    struct EdgeHash {'''
new='''    remove_f.resize(M.facets.nb(),0);
    // 同步新增的面必然受共边请求影响，供下一轮区域生成筛选使用。
    Attribute<bool> quality_shared_active(M.facets.attributes(),"quality_shared_active");
    struct EdgeHash {'''
assert code.count(old)==1;code=code.replace(old,new)
old='''                    M.facets.attributes().copy_item(child,f);remove_f.push_back(0);index_face(child);'''
new='''                    // 保留原来源属性，另标记共边实际修改的子面，避免无关区域重复生成。
                    M.facets.attributes().copy_item(child,f);quality_shared_active[child]=true;remove_f.push_back(0);index_face(child);'''
assert code.count(old)==1;code=code.replace(old,new)
old='''        index_t current_group = 0;'''
new='''        // 初次调用从无活动面开始；递归只继承共边生成和同步实际标记的面。
        Attribute<bool> quality_shared_active(mesh_.facets.attributes(),"quality_shared_active");
        if(quality_neighbor_depth==0) for(index_t f:mesh_.facets) quality_shared_active[f]=false;
        index_t current_group = 0;'''
assert code.count(old)==1;code=code.replace(old,new)
old='''        geo_debug_assert(nb_groups == group_facet.size());'''
new='''        geo_debug_assert(nb_groups == group_facet.size());
        // 整个共面组只要包含一个受影响面就完整再生成，不按单张面截断区域边界。
        vector<bool> active_groups(nb_groups,false);
        for(index_t f:mesh_.facets) if(quality_shared_active[f]) active_groups[facet_group[f]]=true;'''
assert code.count(old)==1;code=code.replace(old,new)
old='''                for(index_t group=b; group<e; ++group) {
                    coplanar.get(group_facet[group],group);'''
new='''                for(index_t group=b; group<e; ++group) {
                    // 初次生成仍覆盖所有组，二次仅处理共边改动实际涉及的完整组。
                    if(!allow_boundary_generation && !active_groups[group]) continue;
                    coplanar.get(group_facet[group],group);'''
assert code.count(old)==1;code=code.replace(old,new)
old='''                facet_group[new_f]=committed_group;'''
new='''                facet_group[new_f]=committed_group;
                // 补边区域本身也纳入二次生成，未修改边界的独立区域不追加活动标记。
                quality_shared_active[new_f]=quality_shared_active[new_f] || modifies_boundary;'''
assert code.count(old)==1;code=code.replace(old,new)
old='''        if(quality_neighbor_depth==0) quality_anchor.destroy();'''
new='''        if(quality_neighbor_depth==0) {
            // 活动标记只服务本次内部再生成，不作为返回网格的永久属性。
            quality_anchor.destroy();quality_shared_active.destroy();
        }'''
assert code.count(old)==1;path.write_text(code.replace(old,new),'utf8')
now=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
manifest=here/'241-共边受影响区域限定再生成源码清单.json'
manifest.write_text(json.dumps({'生成时间':now,'修改时间及修改内容':now+'，首次限定二次生成到共边受影响完整组',
 '文档概述':'初次及最终检查仍覆盖全网格，候选速度与质量尚待实际验证',
 '索引目录':['files','changes'],'prior_manifest_sha256':sha(prior_path),
 'files':{name:sha(output/name) for name in prior['files']},
 'changes':['标记共边补点区域与同步新增面','二次生成完整受影响共面组','未受影响组原面保留','最终全网格检查与回退不变']},ensure_ascii=False,indent=2)+'\n','utf8')
builder=(here/'225-共边邻接索引修订原生独立编译.py').read_text('utf8').replace('第十四轮','第十五轮')
(here/'242-受影响区域限定再生成原生独立编译.py').write_text(builder,'utf8')
controller=(here/'226-共边邻接索引修订编译上传执行.py').read_text('utf8')
for a,b in [('20261006_15','20261006_16'),('第十四轮共边邻接索引成本修订',output.name),
 ('224-共边邻接索引成本修订源码清单.json',manifest.name),
 ('225-共边邻接索引修订原生独立编译.py','242-受影响区域限定再生成原生独立编译.py'),
 ('227-邻接索引修订实际编译执行记录.json','244-受影响区域限定实际编译执行记录.json'),
 ('228-邻接索引修订实际编译控制台日志.txt','245-受影响区域限定实际编译控制台日志.txt'),
 ('229-邻接索引修订实际原生编译记录.json','246-受影响区域限定实际原生编译记录.json'),
 ('第十四轮','第十五轮')]:controller=controller.replace(a,b)
(here/'243-受影响区域限定再生成编译上传执行.py').write_text(controller,'utf8')
print('prepared_complete_affected_groups_without_changing_global_gate')
