"""把安全投影限制在每个新点的支撑平面内，完整网格碰撞与CCD保持运行。"""

import json
import numpy as np
import torch
import trimesh
import warp as wp
from time import perf_counter
from locality_gpu import FixedSystem
from pamo_safe_project import Stage3Config, process
from pamo_safe_project.cg_solver import CGSolver
from pamo_safe_project.kernels.solver_kernels import compute_dot_kernel, update_p_r_z_compute_zr_kernel


@wp.kernel
def project_tangent(values: wp.array(dtype=wp.vec3), fixed: wp.array(dtype=int), normals: wp.array(dtype=wp.vec3)):
    i = wp.tid()
    if fixed[i] != 0:
        values[i] = wp.vec3(0.0)
    else:
        normal = normals[i]
        values[i] = values[i] - normal * (wp.dot(values[i], normal) / wp.dot(normal, normal))


@wp.kernel
def guarded_update_direction(z: wp.array(dtype=wp.vec3), previous: wp.array(dtype=float), current: wp.array(dtype=float), direction: wp.array(dtype=wp.vec3)):
    i = wp.tid()
    beta = float(0.0)
    if previous[0] != 0.0:
        beta = current[0] / previous[0]
    direction[i] = z[i] + beta * direction[i]


class GuardedCG(CGSolver):
    """精确零残差返回零步长，避免作者定长循环对0/0的归一化。"""
    def solve(self):
        gradient = wp.to_torch(self.system.grad)[:self.system.n_particles]
        if not torch.isfinite(gradient).all().item():
            raise RuntimeError("切平面约束梯度非有限")
        if not torch.count_nonzero(gradient).item():
            self.system.p.zero_()
            return
        super().solve()

    def _launch_main_loop(self):
        # 保留作者40次固定迭代及原步长，只为精确零残差的方向更新定义零比例。
        system = self.system
        count = system.n_particles
        for _ in range(system.config.n_cg_iters):
            self.A_v.zero_()
            system._compute_hess_dx(self.v, self.A_v)
            self.v_A_v.zero_()
            wp.launch(compute_dot_kernel, dim=count, inputs=[self.v, self.A_v], outputs=[self.v_A_v])
            wp.copy(self.z_r_last, self.z_r, count=1)
            self.z_r.zero_()
            wp.launch(update_p_r_z_compute_zr_kernel, dim=count,
                inputs=[self.v, self.A_v, self.v_A_v, self.z_r_last, system.hess_diag],
                outputs=[system.p, self.r, self.z, self.z_r])
            wp.launch(guarded_update_direction, dim=count, inputs=[self.z, self.z_r_last, self.z_r, self.v])


class TangentSystem(FixedSystem):
    """在二维切空间求解PAP与Pg，并在CCD之前约束每个方向。"""
    def set_constraints(self, fixed, normals):
        normals = np.asarray(normals, dtype=float)
        if normals.shape != (len(fixed), 3) or not np.isfinite(normals).all():
            raise ValueError("支撑平面法向格式非法")
        if np.any(np.linalg.norm(normals[~fixed], axis=1) < 0.9):
            raise ValueError("自由顶点缺少稳定支撑平面")
        self.set_fixed(fixed)
        self.support_normals = wp.array(normals.astype(np.float32), dtype=wp.vec3, device=self.device)
        self.cg_solver = GuardedCG(self)

    def mask(self, values):
        wp.launch(project_tangent, dim=self.n_particles, inputs=[values, self.fixed_mask, self.support_normals], device=self.device)


def project_on_planes(source, mesh, fixed, normals, origins, system_class=TangentSystem, diagnostics_path=None):
    """五轮作者安全投影；FP64恢复后检查面方向，失败时可保存分阶段数值证据。"""
    if np.all(fixed):
        return mesh.copy(), {"safe_projection_ms": 0.0, "projection": "no_free_vertices_identity"}
    config = Stage3Config()
    # 新数值保护方法显式提供子类，旧方法仍使用同一个默认系统。
    system = system_class(config)
    system.set_constraints(fixed, normals)
    system.bind_fixed_geometry(source, mesh)
    started = perf_counter()
    points, faces = process(source.vertices, source.faces, mesh.vertices, mesh.faces, 5, system=system, config=config)
    system.validate_fixed_geometry()
    torch.cuda.synchronize()
    points = points.astype(np.float64)
    raw = points.copy()
    # 数值保护只在初次求导前新增固定点；与原固定点一样恢复其原始FP64坐标。
    if hasattr(system, "protected_vertices"):
        fixed = fixed.copy()
        fixed[system.protected_vertices] = True
    points[fixed] = mesh.vertices[fixed]
    free = ~fixed
    unit = normals[free] / np.linalg.norm(normals[free], axis=1)[:, None]
    drift = np.sum((points[free] - origins[free]) * unit, axis=1)
    points[free] -= drift[:, None] * unit
    correction = float(np.linalg.norm(points - raw, axis=1).max(initial=0))
    triangles = points[faces]
    signs = np.einsum("ij,ij->i", np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0]), mesh.face_normals)
    if not np.isfinite(points).all() or np.any(signs <= 0):
        # 只记录失败，不回退坐标或改变接受条件；区分CUDA输出与FP64恢复导致的异常。
        if diagnostics_path is not None:
            stages = {}
            for name, values in (("before_projection", mesh.vertices), ("raw_cuda_output", raw), ("restored_planes", points)):
                tri = values[faces]
                crosses = np.cross(tri[:, 1]-tri[:, 0],tri[:, 2]-tri[:, 0])
                stage_signs = np.einsum("ij,ij->i",crosses,mesh.face_normals)
                stages[name] = {"finite_vertices": bool(np.isfinite(values).all()),
                    "nonpositive_orientation_faces": np.flatnonzero(stage_signs <= 0).tolist(),
                    "nonfinite_orientation_faces": np.flatnonzero(~np.isfinite(stage_signs)).tolist(),
                    "minimum_orientation": float(stage_signs.min()) if np.isfinite(stage_signs).all() else None,
                    "area_at_most_1e_12_faces": int(np.count_nonzero(np.linalg.norm(crosses,axis=1)*.5 <= 1e-12))}
            record = {"stages": stages, "fp64_correction_max_mm": correction,
                "collision_protected_vertices": getattr(system,"protected_vertices",[]),
                "collision_protection": getattr(system,"protection_records",[]),
                "remaining_free_vertices": int(free.sum()),
                "scope": "失败数值定位，不代表自交证书，不发布或替换结果"}
            diagnostics_path.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding="utf-8")
        raise RuntimeError("切平面投影出现非有限值或面反向")
    details = {"safe_projection_ms": (perf_counter() - started) * 1000,
        "projection": "full_mesh_author_CCD_with_per_vertex_tangent_subspace", "fp64_correction_max_mm": correction,
        "raw_plane_drift_max_mm": float(np.abs(drift).max(initial=0)), "all_face_orientations_positive": True}
    if hasattr(system, "protected_vertices"):
        details.update(collision_protected_vertices=system.protected_vertices,
                       collision_protection=system.protection_records, remaining_free_vertices=int((~fixed).sum()))
    return trimesh.Trimesh(points, faces, process=False), details
