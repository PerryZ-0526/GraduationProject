"""冻结六个既有开发阻断输入，比较局部向内约束与无该约束的坐标搜索。"""

import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import trimesh

from monotone_precision import probe_repair


def main():
    root = Path(__file__).parent
    source_root = root / "实验结果/20261004_统一来源清理六路线反馈"
    cases = ["development_crossing_slab_01_e1", "development_plan_edge_slab_01_e1",
             "development_shallow_slab_01_e1", "development_vertical_sphere_01_e1",
             "development_stop_resume_sphere_01_e1", "development_repeat_slab_01_e1"]
    output = root / "实验结果/20261004_材料单调精度开发诊断"
    output.mkdir(exist_ok=True)
    target = output / "02-整数候选精度机制诊断.json"
    if target.exists():
        raise FileExistsError("诊断结果已存在，禁止覆盖")
    report = {"生成时间": datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y年%m月%d日%H时%M分%S秒"),
              "修改时间及修改内容": "首次生成；仅CPU开发诊断，未发布候选网格",
              "文档概述": "固定六个开发输入与1e-5毫米位移预算，比较同一坐标搜索的材料约束消融",
              "索引目录": ["参数", "结果"], "参数": {"budget_mm": 1e-5, "offset_radius": 2,
              "integer_solver_limit_seconds": 1.0}, "结果": [],
              "source_hashes": {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                                for name in ("monotone_precision.py", "probe_monotone_precision.py")}}
    paths = [(case, source_root / f"{case}_candidate_input/clean_source.obj") for case in cases]
    for name in ("slab", "sphere"):
        case = f"development_long_{name}_24_e1"
        paths.append((case, root / f"实验结果/20261004_约束质量生成完整冻结验证/long/{case}_candidate_input/clean_source.obj"))
    for case, path in paths:
        mesh = trimesh.load(path, process=False, force="mesh")
        item = {"case": case, "source": str(path.resolve()),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "methods": {}}
        for guard in (False, True):
            _, detail = probe_repair(mesh, material_guard=guard)
            item["methods"]["guarded" if guard else "unguarded"] = detail
        report["结果"].append(item)
        print(case, [(name, data["initial_invalid"], data["remaining_invalid"], len(data["moves"]))
                     for name, data in item["methods"].items()], flush=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
