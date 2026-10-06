"""各轮保持互斥一环，但下一轮重建邻域，避免合法极短边永久被同轮冲突挡住。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json

here=Path(__file__).resolve().parent
source=here/'第十八轮原共面分组单独绑定新边收缩'
output=here/'第十九轮新边收缩互斥邻域逐轮复查';output.mkdir()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
prior_path=here/'313-原共面分组单独新边收缩源码清单.json'
prior=json.loads(prior_path.read_text('utf8'))
for name,digest in prior['files'].items():
    assert sha(source/name)==digest
    (output/name).write_bytes((source/name).read_bytes())
path=output/'mesh_surface_intersection.cpp';code=path.read_text('utf8')
start=code.index('void contract_collapsed_float_edges(')
end=code.index('    void copy_operand(',start)
old=code[start:end]
new=old.replace('void contract_collapsed_float_edges(','index_t contract_collapsed_float_edges(',1)
new=new.replace('if(M.facets.nb_vertices(f)!=3) return;','if(M.facets.nb_vertices(f)!=3) return 0;',1)
new=new.replace('if(candidates.empty()) return;','if(candidates.empty()) return 0;',1)
new=new.replace('if(accepted==0) return;','if(accepted==0) return 0;',1)
marker='''        << " contracted_machine_new_edges=" << nonzero << " max_length=" << max_length << std::endl;
}'''
assert marker in new
new=new.replace(marker,marker[:-1]+'''    // 每个接受收缩删除两张边邻面；返回实际数量，使外层只在有进展时再检查。
    return accepted;
}''',1)
code=code[:start]+new+code[end:]
old='''        // 所有准确交点查询完成后才收缩机器尺度新边，避免中途重排顶点编号。
        contract_collapsed_float_edges(result,quality_original_coordinates);'''
new='''        // 所有准确交点查询完成后才收缩；每轮一环互斥，下一轮重新验证剩余邻域。
        // 仅在实际删除边邻面后继续，面数严格下降，不用放宽链接或法向条件消除冲突。
        while(contract_collapsed_float_edges(result,quality_original_coordinates)!=0) {
        }'''
assert code.count(old)==1;path.write_text(code.replace(old,new),'utf8')
now=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
manifest=here/'336-互斥邻域逐轮新边收缩源码清单.json'
manifest.write_text(json.dumps({'生成时间':now,'修改时间及修改内容':now+'，末阶段逐轮验证剩余极短边',
 '文档概述':'同轮一环互斥保留；各轮重新检查链接与法向；面数严格下降才继续',
 '索引目录':['files','changes'],'prior_manifest_sha256':sha(prior_path),
 'files':{name:sha(output/name) for name in prior['files']},
 'changes':['收缩返回实际接受数','互斥一环跨轮重新检查','无进展即退出，保持所有单边约束']},ensure_ascii=False,indent=2)+'\n','utf8')
builder=(here/'314-原共面分组新边收缩原生独立编译.py').read_text('utf8').replace('第十八轮','第十九轮')
(here/'337-逐轮新边收缩原生独立编译.py').write_text(builder,'utf8')
controller=(here/'315-原共面分组新边收缩编译上传执行.py').read_text('utf8')
for a,b in [('20261006_19','20261006_20'),(source.name,output.name),
 ('313-原共面分组单独新边收缩源码清单.json',manifest.name),
 ('314-原共面分组新边收缩原生独立编译.py','337-逐轮新边收缩原生独立编译.py'),
 ('316-原共面分组新边收缩实际编译执行记录.json','339-逐轮新边收缩实际编译执行记录.json'),
 ('317-原共面分组新边收缩实际编译控制台日志.txt','340-逐轮新边收缩实际编译控制台日志.txt'),
 ('318-原共面分组新边收缩实际原生编译记录.json','341-逐轮新边收缩实际原生编译记录.json'),
 ('第十八轮','第十九轮')]:controller=controller.replace(a,b)
(here/'338-逐轮新边收缩编译上传执行.py').write_text(controller,'utf8')
print('prepared_disjoint_star_contractions_rechecked_until_no_progress')
