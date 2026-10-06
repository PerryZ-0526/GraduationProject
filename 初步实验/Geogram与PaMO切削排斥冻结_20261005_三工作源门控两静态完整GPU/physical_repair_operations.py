"""构造物理面积修复的私有操作，原编码退化修复源码保持不变。"""
from pathlib import Path
from preserved_controller_source import replace_once


def build_sources():
    root = Path(__file__).resolve().parent
    # 只切换操作的退化判据；每次操作的预算和几何保护条件沿用原规则。
    flips = replace_once((root/"locality_retriangulate.py").read_text(encoding="utf-8"),
        "for coordinates in (vertices, vertices.astype(np.float32).astype(np.float64)):",
        "for coordinates in (vertices,):")
    flips = replace_once(flips, "同时检查输入FP64与PaMO实际FP32坐标的退化面积。",
        "仅检查保存FP64物理面积；编码退化仍由固定几何后端独立审查。")
    collapse = replace_once((root/"locality_sliver_collapse.py").read_text(encoding="utf-8"),
        "from locality_retriangulate import invalid_faces", "# 使用同一私有副本的物理面积判据。")
    return {"physical_retriangulate.py": flips, "physical_sliver_collapse.py": collapse}


SOURCES = build_sources()
OPERATIONS = dict(__name__="physical_area_operations")
for name, source in SOURCES.items():
    exec(compile(source, name, "exec"), OPERATIONS)
invalid_faces = OPERATIONS["invalid_faces"]
repair_degenerate = OPERATIONS["repair_degenerate"]
collapse_degenerate = OPERATIONS["collapse_degenerate"]
