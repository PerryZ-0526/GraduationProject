"""仅开启作者已有详细阶段计时，诊断调用不进入正式速度分布。"""
from pathlib import Path

here=Path(__file__).resolve().parent
code=(here/'03-原生布尔质量与阶段计时.cpp').read_text('utf8')
old='''    GEO::mesh_boolean_operation(result, parent, tool, "A-B", simplify ?
        GEO::MESH_BOOL_OPS_DEFAULT : GEO::MESH_BOOL_OPS_NO_SIMPLIFY);'''
new='''    // 诊断执行器只开启作者阶段日志，库、算法和输入不改变，耗时不混入正式配对。
    GEO::mesh_boolean_operation(result, parent, tool, "A-B", GEO::MeshBooleanOperationFlags(
        (simplify ? GEO::MESH_BOOL_OPS_DEFAULT : GEO::MESH_BOOL_OPS_NO_SIMPLIFY) | GEO::MESH_BOOL_OPS_VERBOSE));'''
assert code.count(old)==1
path=here/'217-原生阶段耗时诊断执行器.cpp';assert not path.exists();path.write_text(code.replace(old,new),'utf8')
print('prepared_author_verbose_stage_driver')
