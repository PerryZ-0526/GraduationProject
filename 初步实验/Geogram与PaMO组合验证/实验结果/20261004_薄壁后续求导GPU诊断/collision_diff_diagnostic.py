"""记录原碰撞保护拒绝的求导轮次和能量分项，保持原异常及输出规则。"""
import json
from pathlib import Path
import numpy as np
import torch
import warp as wp
from collision_protected_gpu import CollisionProtectedSystem as OriginalSystem


class CollisionProtectedSystem(OriginalSystem):
    def set_constraints(self,fixed,normals):
        super().set_constraints(fixed,normals)
        self.diagnostic_rows=[]
        self.last_finite_positions=None

    def _compute_diff(self):
        error=None
        try:
            super()._compute_diff()
        except RuntimeError as caught:
            error=caught
        count=self.n_particles
        positions=wp.to_torch(self.q)[:count].detach().cpu().numpy().copy()
        gradient=wp.to_torch(self.grad)[:count]
        diagonal=wp.to_torch(self.hess_diag)[:count]
        free=torch.as_tensor(~self.fixed_host,device=gradient.device)
        bad=free & (~torch.isfinite(gradient).all(dim=1)|~torch.isfinite(diagonal).all(dim=1))
        row={"diff_call":self.diff_calls,"finite_positions":bool(np.isfinite(positions).all()),
            "free_vertices":int(free.sum().item()),"nonfinite_free_vertices":torch.nonzero(bad).flatten().cpu().tolist(),
            "original_error":str(error) if error else None,
            "full_energy":float(self.energy.numpy()[0])}
        if self.last_finite_positions is not None:
            row["max_movement_since_previous_finite_diff_normalized"]=float(np.linalg.norm(positions-self.last_finite_positions,axis=1).max(initial=0))
        if error:
            # 只核对分项导数，保留原接触、完整能量和拒绝，不修改固定点或坐标。
            components=[]
            for name in self.config.energy_calcs:
                grad=wp.zeros(len(self.grad),dtype=wp.vec3,device=self.device)
                diag=wp.zeros(len(self.hess_diag),dtype=wp.vec3,device=self.device)
                self.energy_calcs[name].compute_diff(self.q,-1.0,grad,diag)
                self.mask(grad)
                invalid=free & (~torch.isfinite(wp.to_torch(grad)[:count]).all(dim=1)|
                    ~torch.isfinite(wp.to_torch(diag)[:count]).all(dim=1))
                components.append({"name":name.__name__,"nonfinite_free_vertices":torch.nonzero(invalid).flatten().cpu().tolist()})
            row["component_derivatives"]=components
            np.savez(Path(__file__).with_name("diff_failure_positions.npz"),current=positions,
                previous_finite=self.last_finite_positions,fixed=self.fixed_host)
        elif row["finite_positions"]:
            self.last_finite_positions=positions
        self.diagnostic_rows.append(row)
        Path(__file__).with_name("diff_trace.json").write_text(json.dumps({"rows":self.diagnostic_rows,
            "scope":"原求导流程只读诊断；归一化坐标，非新算法输出或发布"},ensure_ascii=False,indent=2),encoding="utf-8")
        if error:
            raise error
