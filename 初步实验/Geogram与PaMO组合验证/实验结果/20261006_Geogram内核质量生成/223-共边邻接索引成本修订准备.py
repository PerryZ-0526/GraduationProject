"""保留相同生成与判定，用哈希索引替代共边同步中的整网格树索引。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json

here=Path(__file__).resolve().parent
source=here/'第十三轮整体通过后免重复生成'
output=here/'第十四轮共边邻接索引成本修订';output.mkdir()
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
prior_path=here/'201-整体通过后免重复生成源码清单.json'
prior=json.loads(prior_path.read_text('utf8'))
for name,digest in prior['files'].items():
    assert sha(source/name)==digest
    (output/name).write_bytes((source/name).read_bytes())
path=output/'mesh_surface_intersection.cpp';code=path.read_text('utf8')
code=code.replace('#include <set>','#include <set>\n// 共边邻接只按键查询，使用哈希索引避免整网格红黑树插入成本。\n#include <unordered_map>')
old='''    std::map<std::pair<index_t,index_t>,std::set<index_t>> incident;
    std::map<index_t,std::set<index_t>> links;'''
new='''    struct EdgeHash {
        size_t operator()(const std::pair<index_t,index_t>& edge) const {
            size_t a=std::hash<index_t>()(edge.first),b=std::hash<index_t>()(edge.second);
            return a^(b+size_t(0x9e3779b9)+(a<<6)+(a>>2));
        }
    };
    std::unordered_map<std::pair<index_t,index_t>,vector<index_t>,EdgeHash> incident;
    incident.reserve(size_t(M.facets.nb())*2);
    // 顶点编号在同步期间不变；重复邻接最后仍由受影响边集合去重，执行顺序保持。
    vector<vector<index_t>> links(M.vertices.nb());'''
assert code.count(old)==1;code=code.replace(old,new)
old='''            incident[std::minmax(a,b)].insert(f);links[a].insert(b);links[b].insert(a);'''
new='''            // 每个面按编号顺序登记一次，新子面追加仍保持原遍历顺序。
            incident[std::minmax(a,b)].push_back(f);links[a].push_back(b);links[b].push_back(a);'''
assert code.count(old)==1;code=code.replace(old,new)
old='''            const std::set<index_t> faces=incident[edge];'''
new='''            // 同步修改会扩展索引，先复制本边面列表，与旧快照语义相同。
            const vector<index_t> faces=incident[edge];'''
assert code.count(old)==1;path.write_text(code.replace(old,new),'utf8')
now=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
manifest=here/'224-共边邻接索引成本修订源码清单.json'
manifest.write_text(json.dumps({'生成时间':now,'修改时间及修改内容':now+'，首次修订共边同步查询容器',
 '文档概述':'边点、生成参数、接受判据与顺序不改；真实速度改善待执行验证',
 '索引目录':['files','changes'],'prior_manifest_sha256':sha(prior_path),
 'files':{name:sha(output/name) for name in prior['files']},
 'changes':['共边面索引改为预留哈希表','顶点邻接直接编号索引','受影响边仍使用原排序集合','面列表复制快照语义保留']},ensure_ascii=False,indent=2)+'\n','utf8')
builder=(here/'202-整体通过后免重复生成原生独立编译.py').read_text('utf8').replace('第十三轮','第十四轮')
(here/'225-共边邻接索引修订原生独立编译.py').write_text(builder,'utf8')
controller=(here/'203-整体通过后免重复生成编译上传执行.py').read_text('utf8')
for a,b in [('20261006_14','20261006_15'),('第十三轮整体通过后免重复生成',output.name),
 ('201-整体通过后免重复生成源码清单.json',manifest.name),
 ('202-整体通过后免重复生成原生独立编译.py','225-共边邻接索引修订原生独立编译.py'),
 ('204-免重复生成实际编译执行记录.json','227-邻接索引修订实际编译执行记录.json'),
 ('205-免重复生成实际编译控制台日志.txt','228-邻接索引修订实际编译控制台日志.txt'),
 ('206-免重复生成实际原生编译记录.json','229-邻接索引修订实际原生编译记录.json'),
 ('第十三轮','第十四轮')]:controller=controller.replace(a,b)
(here/'226-共边邻接索引修订编译上传执行.py').write_text(controller,'utf8')
print('prepared_same_generation_with_lower_adjacency_index_cost')
