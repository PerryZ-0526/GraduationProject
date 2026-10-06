"""同输入开发检查共面区域重建，报告质量、几何和整网格拓扑。"""

import json
from pathlib import Path
import numpy as np
import trimesh
from planar_patch import rebuild_planar_regions
from locality_masks import make_masks, save_obj_fp64
from geometry_preservation_audit import mesh_valid
from run_constrained_feedback import global_geometry
from audit_followup_candidate import quality_distribution, sha256
from run_geometry_study import now


def main():
    here = Path(__file__).resolve().parent
    prepared = here / "实验结果/20261004_局部维护保存帧开发"
    manifest = json.loads((prepared / "01-保存帧开发批次.json").read_text(encoding="utf-8"))
    output = here / "实验结果/20261004_共面区域重建开发"
    output.mkdir(exist_ok=False)
    report = {"time_beijing": now(), "status": "running", "rows": [], "source_code_sha256": sha256(here / "planar_patch.py"),
              "scope": "八张已见保存输入的CPU质量生成，尚未GPU安全投影或连续反馈"}
    for case in manifest["cases"]:
        folder = prepared / case["case"]
        source = trimesh.load(folder / "source.obj", force="mesh", process=False)
        tool = trimesh.load(folder / "tool.obj", force="mesh", process=False)
        bits = np.array(json.loads((folder / "labels.json").read_text())["operand_bits"])
        active, _ = make_masks(source, bits, tool, "boolean", 2)
        result, labels, operations = rebuild_planar_regions(source, bits, active)
        valid, checks = mesh_valid(result)
        geometry = global_geometry(result, source)
        same_topology = result.euler_number == source.euler_number and len(result.split(only_watertight=False)) == len(source.split(only_watertight=False))
        accepted = valid and same_topology and geometry["probe_max_mm"] <= 1e-7 and checks["fp32_zero_area_faces"] == 0
        path = output / (case["case"] + ".obj")
        save_obj_fp64(result, path)
        (output / (case["case"] + "_labels.json")).write_text(json.dumps({"operand_bits": labels.tolist()}), encoding="utf-8")
        report["rows"].append({"case": case["case"], "input_sha256": sha256(folder / "source.obj"), "output_sha256": sha256(path),
                               "accepted": bool(accepted), "operations": operations, "audit": checks, "geometry": geometry,
                               "before_quality": quality_distribution(source), "after_quality": quality_distribution(result)})
        (output / "01-共面区域重建开发记录.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(case["case"], accepted, checks["zero_area_faces"], checks["fp32_zero_area_faces"], flush=True)
    report["status"] = "completed_with_recorded_failures"
    (output / "01-共面区域重建开发记录.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
