"""只读式GPU故障复现：捕获非有限梯度时逐能量项记录，不输出有效候选。"""
import json
import os
import runpy
import torch
import warp as wp
from tangent_plane_gpu import GuardedCG


original_solve = GuardedCG.solve
solve_calls = 0


def diagnostic_solve(self):
    global solve_calls
    solve_calls += 1
    try:
        original_solve(self)
    except RuntimeError:
        system = self.system
        count = system.n_particles
        q = wp.to_torch(system.q)[:count]
        report = dict(solve_calls=solve_calls,positions_finite=bool(torch.isfinite(q).all().item()),components=[])
        for name in system.config.energy_calcs:
            system.grad.zero_()
            system.hess_diag.zero_()
            system.energy_calcs[name].compute_diff(system.q,-1.0,system.grad,system.hess_diag)
            system.mask(system.grad)
            gradient = wp.to_torch(system.grad)[:count]
            diagonal = wp.to_torch(system.hess_diag)[:count]
            bad = torch.nonzero(~torch.isfinite(gradient).all(dim=1)).flatten()
            report["components"].append(dict(name=str(name),nonfinite_gradient_vertices=int(bad.numel()),
                first_nonfinite_vertex_ids=bad[:100].cpu().tolist(),nonfinite_diagonal_vertices=int((~torch.isfinite(diagonal).all(dim=1)).sum().item())))
        with open(os.environ["GRADIENT_DIAGNOSTIC_OUTPUT"],"w",encoding="utf-8") as stream:
            json.dump(report,stream,ensure_ascii=False,indent=2)
        raise


GuardedCG.solve = diagnostic_solve
runpy.run_path(os.environ["ORIGINAL_PLANAR_WORKER"],run_name="__main__")
