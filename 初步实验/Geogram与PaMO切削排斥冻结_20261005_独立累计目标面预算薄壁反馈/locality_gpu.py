"""在完整闭合网格复用PaMO折叠与安全投影，实现固定外部的局部试验。"""

from pathlib import Path
from time import perf_counter
import importlib.util

import numpy as np
import torch
import trimesh
import warp as wp
import pamo
from pamo_safe_project import Stage3Config, Stage3System, process

from locality_masks import external_contract, make_masks


@wp.kernel
def zero_fixed(values: wp.array(dtype=wp.vec3), fixed: wp.array(dtype=int)):
    i = wp.tid()
    if fixed[i] != 0:
        values[i] = wp.vec3(0.0)


@wp.kernel
def fixed_diagonal(diagonal: wp.array(dtype=wp.vec3), fixed: wp.array(dtype=int)):
    i = wp.tid()
    if fixed[i] != 0:
        diagonal[i] = wp.vec3(1.0)


class FixedSystem(Stage3System):
    """在固定自由度的子空间求解，碰撞能量与CCD仍使用完整网格。"""

    def set_fixed(self, fixed):
        self.fixed_mask = wp.array(np.asarray(fixed, dtype=np.int32), dtype=int, device=self.device)

    def mask(self, values):
        wp.launch(zero_fixed, dim=self.n_particles, inputs=[values, self.fixed_mask], device=self.device)

    def _compute_diff(self):
        super()._compute_diff()
        self.mask(self.grad)
        wp.launch(fixed_diagonal, dim=self.n_particles,
                  inputs=[self.hess_diag, self.fixed_mask], device=self.device)

    def _compute_hess_dx(self, dx, hess_dx):
        self.mask(dx)
        super()._compute_hess_dx(dx, hess_dx)
        self.mask(hess_dx)

    def _clamp_p(self):
        # 在CCD之前清零固定自由度，不能在移动后简单覆盖顶点。
        self.mask(self.p)
        super()._clamp_p()
        self.mask(self.p)


def load_extension(directory):
    path = Path(directory) / "build/pamo_locality_cuda.so"
    spec = importlib.util.spec_from_file_location("pamo_locality_cuda", path)
    extension = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(extension)
    return extension


def run_locality(mesh, bits, tool, mode, extension, rings=2, passes=1, fix_boundary=True):
    """按冻结预算复用作者折叠，再执行五轮受限安全投影。"""
    if passes not in (1, 8):
        raise ValueError("开发预算只登记一次或八次折叠")
    start = perf_counter()
    active, fixed = make_masks(mesh, bits, tool, mode, rings)
    required_fixed = fixed.copy()
    if not fix_boundary:
        # 消融仅固定活动面之外的独占顶点，共享边界允许移动并独立记录越界。
        fixed = np.ones(len(mesh.vertices), dtype=bool)
        fixed[np.unique(mesh.faces[active])] = False
    mask_ms = (perf_counter() - start) * 1000
    original_ids = np.arange(len(mesh.vertices))
    if np.all(fixed):
        # 没有可移动的内部自由度时原样返回，避免零残差求解产生非有限值。
        return mesh.copy(), original_ids, {"mask_ms": mask_ms, "stage2_ms": 0.0, "stage3_ms": 0.0,
                                          "active_faces": int(active.sum()), "active_fraction": float(active.mean()),
                                          "fixed_vertices": int(fixed.sum()), "status": "no_free_vertices",
                                          "fixed_contract": external_contract(mesh, mesh, original_ids, active, fixed),
                                          "fp64_restoration_max_mm": 0.0}
    center = mesh.vertices.mean(axis=0)
    points = torch.from_numpy((mesh.vertices - center).astype(np.float32)).cuda()
    faces = torch.from_numpy(mesh.faces.astype(np.int32)).cuda()
    operator = extension.CUDSP_Free()
    undo = torch.empty(0, dtype=torch.int32, device="cuda")
    scale = float(np.ptp(mesh.vertices, axis=0).max())
    torch.cuda.synchronize()
    start = perf_counter()
    pass_records = []
    unchanged = 0
    for iteration in range(passes):
        # 每次重编号后更新固定掩码与原始索引，不能按第一轮编号继续操作。
        operator.set_fixed_mask(torch.from_numpy(fixed[original_ids].astype(np.int32)).cuda())
        before = len(faces)
        verts, triangles, occupied, mapping, undo = operator.forward(
            points, faces, undo, len(undo), scale, 1e-3, False, iteration == 0)
        keep = occupied.reshape(-1).bool()
        triangles = triangles[triangles[:, 0] >= 0]
        faces = mapping.reshape(-1)[triangles.long()].to(torch.int32)
        points = verts[keep]
        original_ids = original_ids[keep.cpu().numpy()]
        pass_records.append({"iteration": iteration, "before_faces": before, "after_faces": len(faces)})
        unchanged = unchanged + 1 if len(faces) == before else 0
        if unchanged >= 2:
            break
    vertices = points.cpu().numpy().astype(np.float64) + center
    faces_out = faces.cpu().numpy()
    fixed_out = fixed[original_ids]
    # 恢复保留顶点的FP64输入坐标，并在后续独立审计中核查这一恢复。
    vertices[fixed_out] = mesh.vertices[original_ids[fixed_out]]
    torch.cuda.synchronize()
    stage2_ms = (perf_counter() - start) * 1000
    config = Stage3Config()
    system = FixedSystem(config)
    system.set_fixed(fixed_out)
    torch.cuda.synchronize()
    start = perf_counter()
    projected, faces_out = process(mesh.vertices, mesh.faces, vertices, faces_out, 5, system=system, config=config)
    torch.cuda.synchronize()
    stage3_ms = (perf_counter() - start) * 1000
    projected = projected.astype(np.float64)
    restoration = float(np.linalg.norm(projected[fixed_out] - mesh.vertices[original_ids[fixed_out]], axis=1).max(initial=0))
    projected[fixed_out] = mesh.vertices[original_ids[fixed_out]]
    result = trimesh.Trimesh(projected, faces_out, process=False)
    contract = external_contract(mesh, result, original_ids, active, required_fixed)
    if fix_boundary and not contract["passed"]:
        raise RuntimeError("外部固定契约失败: " + str(contract))
    return result, original_ids, {"mask_ms": mask_ms, "stage2_ms": stage2_ms, "stage3_ms": stage3_ms,
                                  "active_faces": int(active.sum()), "active_fraction": float(active.mean()),
                                  "fixed_vertices": int(fixed.sum()), "fixed_contract": contract,
                                  "collapse_pass_budget": passes, "collapse_passes": pass_records,
                                  "boundary_constraint_enabled": fix_boundary,
                                  "fp64_restoration_max_mm": restoration,
                                  "stage1": "skipped_for_audited_closed_boolean_input",
                                  "stage3_collision_scope": "whole_mesh_author_energy_and_ccd"}


def run_full(mesh, use_stage1=True):
    """完整作者分支作为对照；阶段开关明确记录而不混入原版结果。"""
    points = torch.from_numpy(np.asarray(mesh.vertices, dtype=np.float32)).cuda()
    faces = torch.from_numpy(np.asarray(mesh.faces, dtype=np.int32)).cuda()
    start = perf_counter()
    model = pamo.PaMO(mesh, use_stage1=use_stage1, use_stage3=True)
    v, f = model.run(points, faces, ratio=1.0, min_verts=0)
    torch.cuda.synchronize()
    return trimesh.Trimesh(v, f, process=False), {"pamo_run_ms": (perf_counter() - start) * 1000,
                                               "stage1": "original" if use_stage1 else "disabled"}
