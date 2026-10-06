"""完整反馈只替换候选物理面积修复，原版配对沿用原输入处理。"""
from opposed_facet_cleanup import clean_cancel_opposed
from physical_input_repair import repair_physical_input
from preserved_feedback_gate import clean_for_backend as original_clean_for_backend


def clean_for_backend(mesh, bits, branch):
    if branch == "full":
        return original_clean_for_backend(mesh, bits, branch)
    # 来源清理规则不变；修复仍必须经过同保存对象的全量嵌入和后端固定检查。
    clean, labels, details = clean_cancel_opposed(mesh, bits, allow_shared=True)
    repaired, labels, repair = repair_physical_input(clean, labels)
    details["physical_backend_repair"] = repair
    return repaired, labels, details
