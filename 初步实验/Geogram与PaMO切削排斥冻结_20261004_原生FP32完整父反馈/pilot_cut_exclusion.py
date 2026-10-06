"""七张已见保存帧的切削排斥机制开发对照，保留失败和普通最近点投影。"""

import json
import argparse
import shutil
from datetime import datetime
from pathlib import Path
from time import perf_counter
from zoneinfo import ZoneInfo

import numpy as np
import trimesh
from vtkmodules.vtkCommonDataModel import vtkStaticCellLocator
from vtkmodules.vtkCommonCore import reference

from audit_followup_candidate import sha256, quality_distribution
from audit_pamo_outputs import as_polydata
from geometry_preservation_audit import mesh_valid
from run_constrained_feedback import global_geometry
from cut_exclusion import repair_cut_exclusion, supporting_planes
from locality_masks import save_obj_fp64
from probe_removed_material import tool_clearance


def nearest_projection(mesh, source):
    """普通最近点投影对照使用同一源表面，保留相同三角连接。"""
    locator = vtkStaticCellLocator()
    locator.SetDataSet(as_polydata(source))
    locator.BuildLocator()
    points = mesh.vertices.copy()
    closest, cell, sub, square = [0., 0., 0.], reference(0), reference(0), reference(0.)
    for index, point in enumerate(mesh.vertices):
        locator.FindClosestPoint(point, closest, cell, sub, square)
        points[index] = closest
    return trimesh.Trimesh(points, mesh.faces.copy(), process=False)


def vertex_only_projection(mesh, tool):
    """消融仅让每个顶点分别离开工具，检验缺少整面共同支撑的影响。"""
    normals, offsets = supporting_planes(tool)
    points = mesh.vertices.copy()
    signed = points @ normals.T - offsets
    selected = np.argmax(signed, axis=1)
    values = signed[np.arange(len(points)), selected]
    move = np.maximum(0., 1e-8 - values)
    points += move[:, None] * normals[selected]
    return trimesh.Trimesh(points, mesh.faces.copy(), process=False)


def main():
    root = Path(__file__).parent
    prepared = root / "实验结果/20261004_局部维护保存帧开发"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    output = parser.parse_args().output
    output.mkdir(exist_ok=False)
    # 保存真实执行源码，后续迭代不能仅留下不可恢复的摘要。
    for name in ("cut_exclusion.py", "pilot_cut_exclusion.py", "probe_removed_material.py"):
        shutil.copyfile(root / name, output / name)
    report = {"生成时间": datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y年%m月%d日%H时%M分%S秒"),
              "修改时间及修改内容": "首次生成；七张已见帧CPU对照，未回灌或发布",
              "文档概述": "原版PaMO输出、普通最近点投影、逐面半空间排斥的同输入对照",
              "索引目录": ["参数", "结果"], "参数": {"correction_budget_mm": .1, "clearance_mm": 1e-8},
              "source_hashes": {name: sha256(root / name) for name in ("cut_exclusion.py", "pilot_cut_exclusion.py")},
              "结果": [], "status": "running"}
    record = output / "01-半空间排斥开发对照.json"
    record.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    for case in ("crossing_e0", "crossing_e1", "crossing_e2", "crossing_e3",
                 "stop_resume_e0", "stop_resume_e1", "stop_resume_e3"):
        source_path, tool_path = prepared / case / "source.obj", prepared / case / "tool.obj"
        path = prepared / f"取回输出/saved_batch_outputs/{case}/r0_full.obj"
        source, tool, mesh = [trimesh.load(p, process=False, force="mesh") for p in (source_path, tool_path, path)]
        item = {"case": case, "input_hashes": {str(p): sha256(p) for p in (source_path, tool_path, path)}, "methods": {}}
        for method in ("full", "nearest", "vertex_only", "exclusion"):
            start = perf_counter()
            if method == "full":
                candidate, details = mesh.copy(), {}
            elif method == "nearest":
                candidate, details = nearest_projection(mesh, source), {}
            elif method == "vertex_only":
                candidate, details = vertex_only_projection(mesh, tool), {}
            else:
                candidate, details = repair_cut_exclusion(mesh, tool)
            details["correction_cpu_ms"] = (perf_counter() - start) * 1000
            save_obj_fp64(candidate, output / f"{case}_{method}.obj")
            valid, checks = mesh_valid(candidate)
            geometry = global_geometry(candidate, source)
            points = np.concatenate((candidate.vertices, candidate.triangles_center))
            distances = tool_clearance(points, tool)
            item["methods"][method] = {"details": details, "mesh_valid": valid, "mesh_checks": checks,
                                        "geometry": geometry, "quality": quality_distribution(candidate),
                                        "inside_probe_count": int(np.sum(distances < -1e-7)),
                                        "max_inward_plane_depth_mm": max(0., -float(distances.min())),
                                        "max_correction_mm": float(np.linalg.norm(candidate.vertices - mesh.vertices, axis=1).max(initial=0))}
        report["结果"].append(item)
        record.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(case, [(name, data["mesh_valid"], data["inside_probe_count"], data["geometry"]["probe_max_mm"])
                     for name, data in item["methods"].items()], flush=True)
    report["status"] = "completed"
    record.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
