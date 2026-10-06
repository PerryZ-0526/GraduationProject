"""按离散工具邻域和原活动域最近面归属定位小角来源，不修改候选。"""

import json
from pathlib import Path
import numpy as np
import pyvista as pv
import trimesh
from vtkmodules.vtkCommonDataModel import vtkStaticCellLocator
from vtkmodules.vtkCommonCore import reference
from audit_followup_candidate import quality_distribution
from audit_pamo_outputs import as_polydata
from locality_masks import make_masks
from run_geometry_study import now


def main():
    here = Path(__file__).resolve().parent
    batch = here / "实验结果/20261004_接缝共面质量对照_完整依赖"
    report = json.loads((batch / "01-开发记录.json").read_text(encoding="utf-8"))
    inputs = here / "实验结果/20261004_局部维护保存帧开发"
    result = {"time_beijing": now(), "rows": [], "scope": "已见静态输出；最近面分类用于归因，不是严格来源证书"}
    for row in report["rows"]:
        folder = inputs / row["case"]
        source = trimesh.load(folder / "source.obj", force="mesh", process=False)
        tool = trimesh.load(folder / "tool.obj", force="mesh", process=False)
        bits = json.loads((folder / "labels.json").read_text())["operand_bits"]
        active, _ = make_masks(source, bits, tool, "boolean", 2)
        candidate = trimesh.load(batch / (row["case"] + "_" + row["method"]) / "candidate.obj", force="mesh", process=False)
        centers = candidate.triangles_center
        locator = vtkStaticCellLocator()
        locator.SetDataSet(as_polydata(source)); locator.BuildLocator()
        classes = []
        closest, cid, subid, distance = [0.] * 3, reference(0), reference(0), reference(0.)
        for point in centers:
            locator.FindClosestPoint(point, closest, cid, subid, distance)
            classes.append(active[int(cid)])
        classes = np.asarray(classes, bool)
        physical = pv.PolyData(centers).compute_implicit_distance(as_polydata(tool))["implicit_distance"] <= .1
        metrics = {}
        for name, mask in (("source_active_nearest_face", classes), ("source_external_nearest_face", ~classes), ("tool_margin_0_1_mm", physical)):
            metrics[name] = quality_distribution(trimesh.Trimesh(candidate.vertices, candidate.faces[mask], process=False))
        result["rows"].append({"case": row["case"], "method": row["method"], "regions": metrics})
    (batch / "02-小角区域归因.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("diagnosed", len(result["rows"]), flush=True)


if __name__ == "__main__":
    main()
