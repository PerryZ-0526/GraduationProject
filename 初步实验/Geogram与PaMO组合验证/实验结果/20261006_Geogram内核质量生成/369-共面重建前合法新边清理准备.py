"""只在准确共面重建前增加合法新边逐轮清理，末阶段原清理仍保留。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json

here=Path(__file__).resolve().parent
source=here/'第十九轮新边收缩互斥邻域逐轮复查'
output=here/'第二十轮共面重建前合法新边清理';output.mkdir()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
prior_path=here/'336-互斥邻域逐轮新边收缩源码清单.json'
prior=json.loads(prior_path.read_text('utf8'))
for name,digest in prior['files'].items():
    assert sha(source/name)==digest
    (output/name).write_bytes((source/name).read_bytes())
path=output/'mesh_surface_intersection.cpp';code=path.read_text('utf8')
old='''\t) {
\t    I.simplify_coplanar_facets();
\t}
        // 所有准确交点查询完成后才收缩；每轮一环互斥，下一轮重新验证剩余邻域。'''
new='''\t) {
            // 分类已经结束；保留顶点编号和准确点属性，仅先清理满足原约束的机器尺度新边。
            // 共面入口会按顶点准确属性重建当前映射，避免退化边先进入准确CDT约束队列。
            index_t pre_contracted=0;
            for(index_t count=contract_collapsed_float_edges(result,quality_original_coordinates);
                count!=0;count=contract_collapsed_float_edges(result,quality_original_coordinates)) {
                pre_contracted+=count;
            }
            if(pre_contracted!=0) Logger::out("FloatEdgeStage") << "before_coplanar=" << pre_contracted << std::endl;
\t    I.simplify_coplanar_facets();
\t}
        // 所有准确交点查询完成后才收缩；每轮一环互斥，下一轮重新验证剩余邻域。'''
assert code.count(old)==1;path.write_text(code.replace(old,new),'utf8')
now=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
manifest=here/'370-共面重建前合法新边清理源码清单.json'
manifest.write_text(json.dumps({'生成时间':now,'修改时间及修改内容':now+'，准确共面入口前新增同约束清理',
 '文档概述':'保留顶点编号及准确属性；不变机器尺度、原输入保护、链接和法向检查',
 '索引目录':['files','changes'],'prior_manifest_sha256':sha(prior_path),
 'files':{name:sha(output/name) for name in prior['files']},
 'changes':['分类后、准确共面重建前逐轮清理','末阶段清理保留','禁简化诊断路径不变']},ensure_ascii=False,indent=2)+'\n','utf8')
builder=(here/'337-逐轮新边收缩原生独立编译.py').read_text('utf8').replace('第十九轮','第二十轮')
(here/'371-共面重建前清理原生独立编译.py').write_text(builder,'utf8')
controller=(here/'338-逐轮新边收缩编译上传执行.py').read_text('utf8')
for a,b in [('20261006_20','20261006_21'),(source.name,output.name),
 ('336-互斥邻域逐轮新边收缩源码清单.json',manifest.name),
 ('337-逐轮新边收缩原生独立编译.py','371-共面重建前清理原生独立编译.py'),
 ('339-逐轮新边收缩实际编译执行记录.json','373-共面重建前清理实际编译执行记录.json'),
 ('340-逐轮新边收缩实际编译控制台日志.txt','374-共面重建前清理实际编译控制台日志.txt'),
 ('341-逐轮新边收缩实际原生编译记录.json','375-共面重建前清理实际原生编译记录.json'),
 ('第十九轮','第二十轮')]:controller=controller.replace(a,b)
(here/'372-共面重建前清理编译上传执行.py').write_text(controller,'utf8')
print('prepared_machine_new_edge_cleanup_before_exact_coplanar')
