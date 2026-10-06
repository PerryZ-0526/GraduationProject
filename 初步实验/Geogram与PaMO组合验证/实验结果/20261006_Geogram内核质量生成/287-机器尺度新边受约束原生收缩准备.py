"""依据第二刀实际负例，只扩展原生末阶段收缩到机器尺度的新交点边。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json

here=Path(__file__).resolve().parent
source=here/'第十六轮当前差面触发近共面分组'
output=here/'第十七轮机器尺度新边受约束收缩';output.mkdir()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
prior_path=here/'265-当前差面触发近共面分组源码清单.json'
prior=json.loads(prior_path.read_text('utf8'))
for name,digest in prior['files'].items():
    assert sha(source/name)==digest
    (output/name).write_bytes((source/name).read_bytes())
path=output/'mesh_surface_intersection.cpp';code=path.read_text('utf8')
code=code.replace('#include <set>','#include <set>\n// 原输入坐标按双精度逐分量保存，保护不依赖新增点属性传播。\n#include <array>',1)
old='''// 只收缩已经存在于输出面的零长度边，所有保留顶点的双精度坐标均不移动。
void contract_collapsed_float_edges(Mesh& M) {'''
new='''// 输出末阶段只收缩零长或机器尺度新边，所有保留顶点的双精度坐标均不移动。
void contract_collapsed_float_edges(Mesh& M, const std::set<std::array<double,3>>& original) {'''
assert code.count(old)==1;code=code.replace(old,new)
old='''            // 非有限坐标不能被当作合法的零长度边。
            if(std::isfinite(p.x) && std::isfinite(p.y) && std::isfinite(p.z) &&
               p.x==q.x && p.y==q.y && p.z==q.z) candidates.insert(std::minmax(a,b));'''
new='''            // 非有限点拒绝；容差来自机器精度和实际坐标尺度，不使用毫米质量门槛。
            if(!std::isfinite(p.x) || !std::isfinite(p.y) || !std::isfinite(p.z) ||
               !std::isfinite(q.x) || !std::isfinite(q.y) || !std::isfinite(q.z)) continue;
            double scale=std::max({std::abs(p.x),std::abs(p.y),std::abs(p.z),
                                  std::abs(q.x),std::abs(q.y),std::abs(q.z)});
            double bound=128.0*std::numeric_limits<double>::epsilon()*scale;
            if(length(p-q)<=bound) candidates.insert(std::minmax(a,b));'''
assert code.count(old)==1;code=code.replace(old,new)
code=code.replace('''    index_t accepted=0;
    for(auto edge:candidates) {
        index_t a=edge.first,b=edge.second;''','''    index_t accepted=0,nonzero=0;
    double max_length=0.0;
    for(auto edge:candidates) {
        index_t a=edge.first,b=edge.second;
        const vec3& p=M.vertices.point(a);
        const vec3& q=M.vertices.point(b);
        bool exact=(p.x==q.x && p.y==q.y && p.z==q.z);
        bool original_a=original.count({{p.x,p.y,p.z}})!=0;
        bool original_b=original.count({{q.x,q.y,q.z}})!=0;
        // 两个不同原输入点绝不合并；若只有一个原输入点，则必须保留该原坐标。
        if(!exact && original_a && original_b) continue;
        if(!exact && original_b) std::swap(a,b);''',1)
old='''        // 同轮收缩的一环互不相交，防止单项合法但组合改变局部拓扑。
        used.insert(neighborhood.begin(),neighborhood.end());
        redirect[b]=a;++accepted;'''
new='''        // 新边收缩后所有保留邻面须有正面积且法向不翻转，两个边邻面才允许删除。
        bool orientation_ok=true;
        if(!exact) for(index_t f:M.facets) {
            index_t v[3]={M.facets.vertex(f,0),M.facets.vertex(f,1),M.facets.vertex(f,2)};
            bool has_a=(v[0]==a || v[1]==a || v[2]==a);
            bool has_b=(v[0]==b || v[1]==b || v[2]==b);
            if(!has_b || has_a) continue;
            vec3 before[3],after[3];
            for(index_t k=0;k<3;++k) {
                before[k]=M.vertices.point(v[k]);
                after[k]=M.vertices.point(v[k]==b ? a : v[k]);
            }
            vec3 n0=cross(before[1]-before[0],before[2]-before[0]);
            vec3 n1=cross(after[1]-after[0],after[2]-after[0]);
            if(!(dot(n1,n1)>0.0 && dot(n0,n1)>0.0)) {orientation_ok=false;break;}
        }
        if(!orientation_ok) continue;
        // 同轮收缩的一环互不相交，防止单项合法但组合改变局部拓扑。
        used.insert(neighborhood.begin(),neighborhood.end());
        redirect[b]=a;++accepted;
        if(!exact) {++nonzero;max_length=std::max(max_length,length(M.vertices.point(a)-M.vertices.point(b)));}'''
assert code.count(old)==1;code=code.replace(old,new)
code=code.replace('// 删除的面已经是同坐标顶点退化的零面积映像，不删除其他小面积面。',
 '// 只删除通过链接、原输入保护及法向检查的边邻面，不删除其他小面积面。',1)
code=code.replace('''    Logger::out("FloatEdge") << "contracted_zero_length_edges=" << accepted << std::endl;''',
 '''    Logger::out("FloatEdge") << "contracted_zero_length_edges=" << (accepted-nonzero)
        << " contracted_machine_new_edges=" << nonzero << " max_length=" << max_length << std::endl;''',1)
old='''        MeshSurfaceIntersection I(result);'''
new='''        // 在产生交点之前冻结真实输入坐标；新增点是否与原点重合通过坐标集合实际判定。
        std::set<std::array<double,3>> quality_original_coordinates;
        for(index_t v:result.vertices) {
            const vec3& p=result.vertices.point(v);
            quality_original_coordinates.insert({{p.x,p.y,p.z}});
        }
        MeshSurfaceIntersection I(result);'''
assert code.count(old)==1;code=code.replace(old,new)
code=code.replace('''        // 所有准确交点查询完成后再收缩零长度边，避免中途重排顶点编号。
        contract_collapsed_float_edges(result);''',
 '''        // 所有准确交点查询完成后才收缩机器尺度新边，避免中途重排顶点编号。
        contract_collapsed_float_edges(result,quality_original_coordinates);''',1)
path.write_text(code,'utf8')
now=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
manifest=here/'288-机器尺度新边受约束收缩源码清单.json'
manifest.write_text(json.dumps({'生成时间':now,'修改时间及修改内容':now+'，首次原生机器尺度新边收缩',
 '文档概述':'仅输出末阶段；保护原输入坐标并检查链接、邻面法向和同轮一环独立',
 '索引目录':['files','changes'],'prior_manifest_sha256':sha(prior_path),
 'files':{name:sha(output/name) for name in prior['files']},
 'changes':['原输入坐标冻结','新增非零边机器尺度容差','不同原点禁止合并','邻面正面积且法向不翻转']},ensure_ascii=False,indent=2)+'\n','utf8')
builder=(here/'266-当前差面触发分组原生独立编译.py').read_text('utf8').replace('第十六轮','第十七轮')
# 新目录使用自己的输入副本，不能通过旧输入软链接写入新增失败例。
builder=builder.replace("(root/'inputs').symlink_to(prior/'inputs')","shutil.copytree(prior/'inputs',root/'inputs')")
(here/'289-机器尺度新边原生独立编译.py').write_text(builder,'utf8')
controller=(here/'267-当前差面触发分组编译上传执行.py').read_text('utf8')
for a,b in [('20261006_17','20261006_18'),(source.name,output.name),
 ('265-当前差面触发近共面分组源码清单.json',manifest.name),
 ('266-当前差面触发分组原生独立编译.py','289-机器尺度新边原生独立编译.py'),
 ('268-当前差面分组实际编译执行记录.json','291-机器尺度新边实际编译执行记录.json'),
 ('269-当前差面分组实际编译控制台日志.txt','292-机器尺度新边实际编译控制台日志.txt'),
 ('270-当前差面分组实际原生编译记录.json','293-机器尺度新边实际原生编译记录.json'),
 ('第十六轮','第十七轮')]:controller=controller.replace(a,b)
(here/'290-机器尺度新边编译上传执行.py').write_text(controller,'utf8')
print('prepared_native_machine_edge_contraction')
