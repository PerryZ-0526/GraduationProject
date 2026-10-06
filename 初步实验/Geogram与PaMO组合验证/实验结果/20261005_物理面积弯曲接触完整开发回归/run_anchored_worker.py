"""共面区域质量生成后执行PaMO完整碰撞投影，固定切削邻域之外的顶点。"""

import argparse
import json
from pathlib import Path
from time import perf_counter
import numpy as np
import trimesh
from planar_patch import rebuild_planar_regions
from locality_masks import make_masks, save_obj_fp64
from constrained_quality import safe_project


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "labels", "tool", "executable", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--method", required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    source = trimesh.load(args.source, force="mesh", process=False)
    tool = trimesh.load(args.tool, force="mesh", process=False)
    started = perf_counter()
    if args.method == "full":
        from locality_gpu import run_full
        result, details = run_full(source)
    else:
        bits = json.loads(args.labels.read_text())["operand_bits"]
        # 共同来源仅对显式命名的新开发方法开启，旧方法保留原规则。
        shared = args.method.endswith("_shared")
        active, _ = make_masks(source, bits, tool, "boolean", 4 if args.method.startswith("expanded") else 2, allow_shared=shared)
        # 面积保护单列方法名，旧批次的区域接受规则保持原样。
        mesh, labels, details = rebuild_planar_regions(source, bits, active, allow_shared=shared,
            min_area_mm2=1e-12 if "areaguard" in args.method else 0.0)
        ids = np.asarray(details["vertex_original_ids"])
        # 凸工具沿用原面平面余量；非凸工具使用实际表面距离带。
        if tool.is_convex:
            normals = tool.face_normals
            offsets = np.einsum("ij,ij->i", tool.triangles_center, normals)
            near = np.zeros(len(mesh.vertices), bool)
            for start in range(0, len(mesh.vertices), 2048):
                signed = mesh.vertices[start:start + 2048] @ normals.T - offsets
                near[start:start + 2048] = np.max(signed, axis=1) <= .1
        else:
            from tool_surface_band import surface_band
            near = surface_band(mesh.vertices, tool, .1)
        outside_faces = ~np.all(near[mesh.faces], axis=1)
        fixed = ids >= 0
        fixed[np.unique(mesh.faces[outside_faces])] = True
        # 编码退化仅允许全部原固定几何顶点，包含自由点的面在GPU求解前拒绝。
        from preserved_geometry_precondition import require_fixed_degenerate_faces
        geometry_scale = 1.0 / np.ptp(source.vertices, axis=0).max()
        geometry_translation = -source.vertices.mean(axis=0)*geometry_scale
        details["fixed_geometry_arithmetic_precondition"] = require_fixed_degenerate_faces(
            mesh.vertices, mesh.faces, fixed, geometry_scale, geometry_translation)
        before = mesh.vertices.copy()
        save_obj_fp64(mesh, args.output / "before_projection.obj")
        # 新共同来源方法沿用相同切空间求解及完整碰撞投影。
        if "tangent" in args.method:
            from tangent_preserved_gpu import project_on_planes
            # 碰撞数值保护另立方法名；失败诊断只写证据，不改变固定规则或接受条件。
            if "protected" in args.method:
                from anchored_geometry_system import CollisionProtectedSystem
                result, projection = project_on_planes(source, mesh, fixed,
                    np.asarray(details["vertex_support_normals"]), np.asarray(details["vertex_support_origins"]),
                    system_class=CollisionProtectedSystem, diagnostics_path=args.output / "projection_failure.json")
                fixed[projection.get("collision_protected_vertices",[])] = True
            else:
                result, projection = project_on_planes(source, mesh, fixed,
                    np.asarray(details["vertex_support_normals"]), np.asarray(details["vertex_support_origins"]))
        else:
            result, projection = safe_project(source, mesh, ids, fixed)
        new_fixed = fixed & (ids < 0)
        correction = float(np.linalg.norm(result.vertices[new_fixed] - before[new_fixed], axis=1).max(initial=0))
        # 作者CUDA坐标为FP32；新增固定点也恢复到质量生成的FP64位置，并记录修正。
        result.vertices[new_fixed] = before[new_fixed]
        details.update(projection, new_fixed_fp64_restoration_max_mm=correction,
                       free_vertices=int((~fixed).sum()), region_source_bits=labels.tolist(),
                       free_domain="convex_polyhedral_face_plane_margin_0_1_mm" if tool.is_convex else "closed_tool_surface_distance_band_0_1_mm",
                       fixed_contract={"passed": bool(np.array_equal(result.vertices[fixed], before[fixed])),
                                       "kind": "source_vertices_and_all_faces_outside_convex_tool_margin_fixed"})
        if not details["fixed_contract"]["passed"]:
            raise RuntimeError("平面候选的固定顶点契约失败")
    if not np.isfinite(result.vertices).all() or np.any(result.area_faces <= 1e-12):
        raise RuntimeError("平面候选非有限或退化输出")
    save_obj_fp64(result, args.output / "candidate.obj")
    details.update(method=args.method, maintenance_ms=(perf_counter() - started) * 1000, status="pending_independent_audit")
    (args.output / "details.json").write_text(json.dumps(details, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
