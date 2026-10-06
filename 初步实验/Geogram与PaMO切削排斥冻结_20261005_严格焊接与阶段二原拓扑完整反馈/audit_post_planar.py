"""在已保存安全投影输出上验证固定曲线保护下的共面质量维护。"""

import json
from pathlib import Path
import numpy as np
import trimesh
from adaptive_seam import subdivide_constraints
from planar_quality import improve_planar
from locality_masks import make_masks, save_obj_fp64
from constrained_quality import fixed_surface_contract
from geometry_preservation_audit import mesh_valid
from run_constrained_feedback import global_geometry
from audit_followup_candidate import quality_distribution, sha256
from run_geometry_study import now


def main():
    here = Path(__file__).resolve().parent
    batch = here / "实验结果/20261004_接缝共面质量对照_完整依赖"
    old = json.loads((batch / "01-开发记录.json").read_text(encoding="utf-8"))
    output = here / "实验结果/20261004_投影后受保护共面维护"
    output.mkdir(exist_ok=False)
    report = {"time_beijing": now(), "scope": "六张已见保存输出，CPU维护审计；非新增GPU投影或连续发布", "rows": []}
    for row in old["rows"]:
        if row["method"] == "full":
            continue
        inputs = here / "实验结果/20261004_局部维护保存帧开发" / row["case"]
        source = trimesh.load(inputs / "source.obj", force="mesh", process=False)
        tool = trimesh.load(inputs / "tool.obj", force="mesh", process=False)
        bits = json.loads((inputs / "labels.json").read_text())["operand_bits"]
        active, fixed = make_masks(source, bits, tool, "boolean", 2)
        relevant = np.unique(source.faces[active])
        lengths = source.edges_unique_length[np.all(np.isin(source.edges_unique, relevant), axis=1)]
        target = float(np.median(lengths))
        prepared, labels, active, fixed, _, _ = subdivide_constraints(source, bits, active, fixed, target)
        if row["method"] == "adaptive_planar":
            prepared, _ = improve_planar(prepared, labels, active)
        # 与CGAL入口相同地保护来源交线、活动边界和45度锐边端点。
        pairs = prepared.face_adjacency
        eligible = np.any(active[pairs], axis=1)
        constrained = (active[pairs[:, 0]] != active[pairs[:, 1]]) | (labels[pairs[:, 0]] != labels[pairs[:, 1]])
        constrained |= np.einsum("ij,ij->i", prepared.face_normals[pairs[:, 0]], prepared.face_normals[pairs[:, 1]]) < np.cos(np.pi / 4)
        fixed[np.unique(prepared.face_adjacency_edges[eligible & constrained])] = True
        path = batch / (row["case"] + "_" + row["method"]) / "candidate.obj"
        candidate = trimesh.load(path, force="mesh", process=False)
        coordinates = {tuple(v) for v in prepared.vertices[fixed]}
        protected = np.array([tuple(v) in coordinates for v in candidate.vertices])
        result, operations = improve_planar(candidate, np.ones(len(candidate.faces), int), np.ones(len(candidate.faces), bool), protected_vertices=protected)
        valid, checks = mesh_valid(result)
        geometry = global_geometry(result, candidate)
        contract = fixed_surface_contract(prepared, result, active, fixed)
        accepted = valid and contract["passed"] and geometry["probe_max_mm"] <= 1e-7
        target_path = output / (row["case"] + "_" + row["method"] + ".obj")
        save_obj_fp64(result, target_path)
        record = {"case": row["case"], "method": row["method"], "source_sha256": sha256(path), "output_sha256": sha256(target_path),
                  "accepted": bool(accepted), "protected_vertices": int(protected.sum()), "operations": operations,
                  "before_quality": quality_distribution(candidate), "after_quality": quality_distribution(result),
                  "audit": checks, "geometry": geometry, "fixed_contract": contract}
        report["rows"].append(record)
        (output / "01-投影后共面维护诊断.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(row["case"], row["method"], accepted, len(operations["flips"]), flush=True)
    report["status"] = "completed"
    (output / "01-投影后共面维护诊断.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
