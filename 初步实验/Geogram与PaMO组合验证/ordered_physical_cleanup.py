"""新版本在反向面抵消后先修复物理退化，再检查原拓扑和几何预算。"""
from pathlib import Path
from physical_input_repair import repair_physical_input
from preserved_controller_source import replace_once
from preserved_feedback_gate import clean_for_backend as original_clean_for_backend


SOURCE = Path(__file__).with_name('opposed_facet_cleanup.py').read_text(encoding='utf-8')
SOURCE = 'from physical_input_repair import repair_physical_input\n'+SOURCE
SOURCE = replace_once(SOURCE, '    valid,metrics=mesh_valid_exact_contacts(candidate)\n',
    '''    # 新顺序只调用既有有限物理修复，修复不合格仍拒绝，最终精确审计另行执行。
    candidate, repaired_bits, repair = repair_physical_input(candidate, bits[keep])
    if not repair["accepted_for_fixed_geometry_backend"]:
        raise ValueError("反向面抵消后物理修复不通过")
    valid,metrics=mesh_valid_exact_contacts(candidate)
''')
# 编码退化不在物理清理处拒绝，必须由新入口的初态锚点与原后端契约处理。
SOURCE = replace_once(SOURCE, 'if not valid or metrics["fp32_zero_area_faces"] or not topology:',
    'if not valid or not topology:')
SOURCE = replace_once(SOURCE, 'return candidate,bits[keep],', 'return candidate,repaired_bits,')
SOURCE = replace_once(SOURCE, '"surviving_original_face_ids":np.flatnonzero(keep).tolist(),',
    '"pre_repair_surviving_original_face_ids":np.flatnonzero(keep).tolist(),\n'
    '        "physical_repair_before_joint_check":repair,\n'
    '        "face_index_scope":"原始面编号仅对应修复前抵消对象，不冒充修复后面对应",')
namespace = dict(__name__='ordered_physical_cleanup_snapshot')
exec(compile(SOURCE, 'ordered_physical_cleanup_snapshot.py', 'exec'), namespace)
ordered_cancel_opposed = namespace['clean_cancel_opposed']


def clean_for_backend(mesh, bits, branch):
    """原版分支不改；候选仍须通过原保存对象精确门控与GPU检查。"""
    if branch == 'full':
        return original_clean_for_backend(mesh, bits, branch)
    clean, labels, details = ordered_cancel_opposed(mesh, bits, allow_shared=True)
    # 无重复面的路径仍调用原物理修复；已修复的对象不会增加操作预算。
    repaired, labels, repair = repair_physical_input(clean, labels)
    details['physical_backend_repair'] = repair
    details['cleanup_order_version'] = 'cancel_physical_repair_joint_check_v1'
    return repaired, labels, details
