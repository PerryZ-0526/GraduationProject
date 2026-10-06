"""物理面积修复沿用原输入保护与预算，编码退化交后端独立审查。"""
from pathlib import Path
from preserved_controller_source import replace_once


SOURCE = Path(__file__).with_name("preserved_input_repair.py").read_text(encoding="utf-8")
SOURCE = replace_once(SOURCE,
    "from locality_retriangulate import invalid_faces,repair_degenerate\nfrom locality_sliver_collapse import collapse_degenerate",
    "from physical_repair_operations import invalid_faces,repair_degenerate,collapse_degenerate")
SOURCE = replace_once(SOURCE, "FP64物理面积门槛保持；FP32退化仅可进入原固定几何后端并验证所有相关自由度固定",
    "仅按FP64物理面积修复；FP32退化数量保留，须交原固定几何后端验证相关顶点全部固定")
# 私有命名空间保留最终拓扑、物理面积、几何预算及未通过时返回原输入的行为。
namespace = dict(__name__="physical_input_repair_snapshot")
exec(compile(SOURCE, "physical_input_repair_snapshot.py", "exec"), namespace)
repair_physical_input = namespace["repair_preserved_input"]
