"""原固定接触的几何保留系统，真实零距离或固定点运动必须拒绝。"""
import numpy as np
import torch
import warp as wp
from precision_gradient_system import CollisionProtectedSystem as GradientSystem
from preserved_collision_install import install_preserved_calculators


class CollisionProtectedSystem(GradientSystem):
    def __init__(self, config):
        super().__init__(config)
        install_preserved_calculators(self)

    def bind_fixed_geometry(self, source, mesh):
        scale = 1.0 / np.ptp(source.vertices, axis=0).max()
        translation = -source.vertices.mean(axis=0)*scale
        self.original_fixed_host = self.fixed_host.copy()
        self.original_fixed_mask = wp.array(self.original_fixed_host.astype(np.int32),dtype=int,device=self.device)
        self.original_fixed_mm = wp.array(mesh.vertices.copy(),dtype=wp.vec3d,device=self.device)
        self.geometry_scale = np.float64(scale*self.config.system_scale)
        self.geometry_failures = wp.zeros(2,dtype=int,device=self.device)
        # 与作者process的两次坐标变换顺序完全一致，不用推测初始CUDA坐标。
        encoded = ((mesh.vertices*scale+translation)*self.config.system_scale).astype(np.float32)
        self.original_fixed_encoded = torch.as_tensor(encoded,device=self.device)

    def validate_fixed_geometry(self, check_direction=False):
        if self.n_particles != len(self.original_fixed_host):
            raise RuntimeError("原固定几何绑定粒子数改变")
        fixed = torch.as_tensor(self.original_fixed_host,device=self.device)
        current = wp.to_torch(self.q)[:self.n_particles]
        if not torch.equal(current[fixed],self.original_fixed_encoded[fixed]):
            raise RuntimeError("原固定几何在CUDA中发生移动")
        failures = self.geometry_failures.numpy()
        if np.any(failures):
            raise RuntimeError("原固定接触真实零距离或CCD非零速度："+str(failures.tolist()))
        if check_direction and torch.count_nonzero(wp.to_torch(self.p)[:self.n_particles][fixed]).item():
            raise RuntimeError("CCD前原固定自由度非零")

    def _compute_diff(self):
        self.validate_fixed_geometry()
        super()._compute_diff()
        self.validate_fixed_geometry()
        if not np.isfinite(self.energy.numpy()[0]):
            raise RuntimeError("原几何分支后完整总能量仍非有限")

    def _ccd(self):
        self.validate_fixed_geometry(check_direction=True)
        super()._ccd()
        self.validate_fixed_geometry(check_direction=True)
