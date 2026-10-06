"""自动活动域的CGAL质量生成与PaMO受限安全投影；不裁开放面片。"""

import json
from pathlib import Path
import subprocess
from time import perf_counter

import numpy as np
import trimesh

from locality_masks import make_masks, save_obj_fp64


def fixed_surface_contract(source, candidate, active, fixed):
    """以FP64坐标与有向面集合核对外部，允许活动区出现新顶点。"""
    def key(points):
        vertices = tuple(tuple(float(x) for x in p) for p in points)
        return min(vertices, vertices[1:] + vertices[:1], vertices[2:] + vertices[:2])
    before = {key(t) for t in source.triangles[~active]}
    after = {key(t) for t in candidate.triangles}
    vertices = {tuple(float(x) for x in v) for v in candidate.vertices}
    missing = sum(tuple(float(x) for x in v) not in vertices for v in source.vertices[fixed])
    return {"passed": before <= after and missing == 0, "external_faces": len(before),
            "external_faces_retained": len(before & after), "missing_fixed_vertices": missing}


def generate_quality(source, bits, tool, mode, directory, executable, rings=2, fix_boundary=True):
    """一次固定预算的受约束重网格；目标长度来自输入活动边，不读评测答案。"""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    started = perf_counter()
    active, fixed = make_masks(source, bits, tool, mode, rings)
    required_fixed = fixed.copy()
    if not fix_boundary:
        fixed[np.unique(source.faces[active])] = False
    # 全量对照共用同一输入尺度规则，实际长约束边调整另记录，不伪称相同目标长度。
    relevant = np.unique(source.faces[active])
    edge_mask = np.all(np.isin(source.edges_unique, relevant), axis=1)
    lengths = source.edges_unique_length[edge_mask]
    requested = float(np.median(lengths)) if len(lengths) else float(np.median(source.edges_unique_length))
    save_obj_fp64(source, directory / "source.obj")
    with (directory / "mask.txt").open("w") as stream:
        stream.write(f"{len(source.vertices)} {len(source.faces)} {int(fix_boundary)}\n")
        stream.writelines(f"{int(v)}\n" for v in fixed)
        stream.writelines(f"{int(a)} {int(b)}\n" for a, b in zip(active, bits))
    command = [str(executable), str(directory / "source.obj"), str(directory / "mask.txt"),
               str(directory / "remeshed.obj"), str(requested), str(directory / "mapping.txt")]
    run = subprocess.run(command, capture_output=True, text=True, timeout=300)
    (directory / "remesh.log").write_text(run.stdout + run.stderr, encoding="utf-8")
    if run.returncode:
        raise RuntimeError(f"CGAL质量生成失败：{run.returncode}")
    mesh = trimesh.load(directory / "remeshed.obj", force="mesh", process=False)
    lines = (directory / "mapping.txt").read_text().splitlines()
    actual, protected = map(float, lines[0].split())
    mapping = np.array([list(map(int, line.split())) for line in lines[1:]])
    if mapping.shape != (len(mesh.vertices), 2):
        raise ValueError("CGAL顶点映射尺寸错误")
    ids, output_fixed = mapping[:, 0], mapping[:, 1].astype(bool)
    retained = (ids >= 0) & output_fixed
    restoration = float(np.linalg.norm(mesh.vertices[retained] - source.vertices[ids[retained]], axis=1).max(initial=0))
    mesh.vertices[retained] = source.vertices[ids[retained]]
    details = {"quality_generation_ms": (perf_counter() - started) * 1000,
               "requested_edge_length_mm": requested, "actual_edge_length_mm": actual,
               "max_protected_edge_mm": protected, "active_fraction": float(active.mean()),
               "input_faces": len(source.faces), "output_faces": len(mesh.faces),
               "fp64_restoration_max_mm": restoration, "iterations": 3,
               "fixed_contract_before_projection": fixed_surface_contract(source, mesh, active, required_fixed)}
    return mesh, ids, output_fixed, active, required_fixed, details


def safe_project(source, mesh, ids, fixed):
    """完整网格执行作者GPU碰撞检查，固定掩码约束整个投影求解过程。"""
    if np.all(fixed):
        # 零自由度不进入迭代线性求解，避免零残差归一化产生非有限值。
        return mesh.copy(), {"safe_projection_ms": 0.0, "projection_fp64_restoration_max_mm": 0.0,
                            "collision_scope": "no_free_vertices_identity_after_remesh"}
    import torch
    from locality_gpu import FixedSystem
    from pamo_safe_project import Stage3Config, process
    config = Stage3Config()
    system = FixedSystem(config)
    system.set_fixed(fixed)
    started = perf_counter()
    points, faces = process(source.vertices, source.faces, mesh.vertices, mesh.faces, 5, system=system, config=config)
    torch.cuda.synchronize()
    points = points.astype(np.float64)
    retained = fixed & (ids >= 0)
    restoration = float(np.linalg.norm(points[retained] - source.vertices[ids[retained]], axis=1).max(initial=0))
    points[retained] = source.vertices[ids[retained]]
    return trimesh.Trimesh(points, faces, process=False), {
        "safe_projection_ms": (perf_counter() - started) * 1000, "projection_fp64_restoration_max_mm": restoration,
        "collision_scope": "whole_mesh_author_energy_and_ccd"}
