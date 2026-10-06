"""第二版在已经查看的首版21输入上开发；这些输入不能再作为第二版独立评测。"""

import json
from pathlib import Path
import shutil

import numpy as np
import trimesh

from adaptive_cut_exclusion import adaptive_exclusion
from audit_followup_candidate import sha256, quality_distribution
from locality_masks import save_obj_fp64
from run_constrained_batch import HERE
from run_geometry_study import save, now
from probe_removed_material import tool_clearance


def main():
    assets = HERE.parent / "可复用磨削测试集/连续输入_v1"
    original = HERE / "实验结果/20261004_切削排斥21几何体独立静态验证"
    output = HERE / "实验结果/20261004_自适应切削排斥第二版开发"
    output.mkdir(exist_ok=False)
    for name in ("adaptive_cut_exclusion.py", "cut_exclusion.py", "pilot_adaptive_cut_exclusion.py", "pilot_cut_exclusion.py"):
        shutil.copyfile(HERE / name, output / name)
    routes = {r["id"]: r for r in json.loads((assets / "01-完整范围冻结清单.json").read_text(encoding="utf-8"))["routes"]}
    first = json.loads((original / "02-独立静态执行与审计.json").read_text(encoding="utf-8"))
    report = {"生成时间": now(), "修改时间及修改内容": "首次生成，只用已见首版输出开发，不产生新GPU帧",
              "文档概述": "累计参照目标、信赖球和至多两级证据驱动细分；首版保留集对本版已属开发输入",
              "索引目录": ["parameters", "rows"], "parameters": {"max_levels": 2, "budget_mm": .1, "clearance_mm": 1e-8},
              "source_hashes": {p.name: sha256(p) for p in output.glob("*.py")}, "rows": [], "status": "running"}
    record = output / "01-自适应切削排斥开发.json"
    save(record, report)
    for row in first["rows"]:
        case = row["route"]
        source_path, full_path = original / case / "source.obj", original / case / "full.obj"
        tool_path = assets / "inputs" / routes[case]["prefix_tools"][0]["mesh"]
        source, full, tool = [trimesh.load(p, force="mesh", process=False) for p in (source_path, full_path, tool_path)]
        candidate, details = adaptive_exclusion(full, [tool], source)
        save_obj_fp64(candidate, output / f"{case}_candidate.obj")
        probes = tool_clearance(np.concatenate((candidate.vertices, candidate.triangles_center)), tool)
        item = {"case": case, "details": details, "quality": quality_distribution(candidate),
                "input_hashes": {str(p): sha256(p) for p in (source_path, full_path, tool_path)},
                "inside_probe_count": int(np.sum(probes < -1e-7)),
                "full_quality": row["methods"]["full"]["quality"]}
        report["rows"].append(item)
        save(record, report)
        print(case, details["accepted"], [(a["level"], a["exclusion"].get("reason"), a["mesh_valid"],
                                          a["geometry"]["probe_max_mm"]) for a in details["attempts"]], flush=True)
    report["status"] = "completed_with_recorded_failures"
    save(record, report)


if __name__ == "__main__":
    main()
