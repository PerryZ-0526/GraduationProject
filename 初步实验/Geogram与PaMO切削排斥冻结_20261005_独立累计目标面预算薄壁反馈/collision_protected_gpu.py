"""只在初次求导时固定碰撞项数值失稳的新增自由点，保留完整能量及CCD。"""
import numpy as np
import torch
import warp as wp
from tangent_plane_gpu import TangentSystem


class CollisionProtectedSystem(TangentSystem):
    def set_constraints(self, fixed, normals):
        super().set_constraints(fixed,normals)
        self.fixed_host = np.asarray(fixed,bool).copy()
        self.protected_vertices = []
        self.protection_records = []
        self.diff_calls = 0

    def _compute_diff(self):
        self.diff_calls += 1
        super()._compute_diff()
        count = self.n_particles
        gradient = wp.to_torch(self.grad)[:count]
        diagonal = wp.to_torch(self.hess_diag)[:count]
        free = torch.as_tensor(~self.fixed_host,device=gradient.device)
        bad = free & (~torch.isfinite(gradient).all(dim=1) | ~torch.isfinite(diagonal).all(dim=1))
        if not bad.any().item():
            return
        if self.diff_calls != 1 or not torch.isfinite(wp.to_torch(self.q)[:count]).all().item():
            raise RuntimeError("数值保护只允许在有限初态第一次求导前固定自由点")
        component_records = []
        collision_bad = torch.zeros_like(bad)
        # 逐项验证原因，不能把其他能量的非有限值归为碰撞项并继续执行。
        for name in self.config.energy_calcs:
            temporary_grad = wp.zeros(len(self.grad),dtype=wp.vec3,device=self.device)
            temporary_diag = wp.zeros(len(self.hess_diag),dtype=wp.vec3,device=self.device)
            self.energy_calcs[name].compute_diff(self.q,-1.0,temporary_grad,temporary_diag)
            self.mask(temporary_grad)
            component_bad = free & (~torch.isfinite(wp.to_torch(temporary_grad)[:count]).all(dim=1) |
                                    ~torch.isfinite(wp.to_torch(temporary_diag)[:count]).all(dim=1))
            component_records.append(dict(name=str(name),nonfinite_free_vertices=int(component_bad.sum().item())))
            if "Collision" in name.__name__:
                collision_bad |= component_bad
            elif component_bad.any().item():
                raise RuntimeError("非碰撞能量失稳，拒绝数值保护")
        if (bad & ~collision_bad).any().item() or not collision_bad.any().item():
            raise RuntimeError("总导数失稳不能由碰撞项解释，拒绝数值保护")
        self.protected_vertices = torch.nonzero(collision_bad).flatten().cpu().tolist()
        self.fixed_host[self.protected_vertices] = True
        self.set_fixed(self.fixed_host)
        self.protection_records.append(dict(first_diff=True,protected_vertices=self.protected_vertices,
                                            component_records=component_records))
        # 重新计算完整导数后开始原求解与CCD，不删除接触、不替换异常值。
        super()._compute_diff()
        free = torch.as_tensor(~self.fixed_host,device=gradient.device)
        if (free & (~torch.isfinite(wp.to_torch(self.grad)[:count]).all(dim=1) |
                    ~torch.isfinite(wp.to_torch(self.hess_diag)[:count]).all(dim=1))).any().item():
            raise RuntimeError("新增固定点后完整导数仍非有限")
