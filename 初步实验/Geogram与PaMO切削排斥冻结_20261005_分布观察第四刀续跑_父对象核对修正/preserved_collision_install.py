"""隔离编译固定接触分支并绑定单个系统，完整检测列表保持原样。"""
import importlib.util
import json
from pathlib import Path
import sys
from types import MethodType
import warp as wp
from preserved_collision_source import preserve_energy_source, preserve_ccd_source


def install_preserved_calculators(system):
    directory = Path(__file__).with_name("preserved_geometry_snapshots")
    directory.mkdir(exist_ok=True)
    energy_name = "pamo_safe_project.kernels.energy_kernels.precision_gradient_collision_energy"
    ccd_name = "pamo_safe_project.kernels.precision_ccd_kernels"
    clones = []
    for name, transform, suffix in ((energy_name, preserve_energy_source, "preserved_collision_energy"),
                                    (ccd_name, preserve_ccd_source, "preserved_ccd")):
        original = sys.modules[name]
        source = transform(Path(original.__file__).read_text(encoding="utf-8"))
        path = directory / (suffix+".py")
        path.write_text(source, encoding="utf-8")
        identity = name.rsplit(".", 1)[0]+"."+suffix
        spec = importlib.util.spec_from_file_location(identity, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[identity] = module
        spec.loader.exec_module(module)
        clones.append(module)
    energy, ccd = clones

    def extra(calculator):
        s = calculator.system
        return [s.original_fixed_mask, s.original_fixed_mm, s.geometry_scale, s.geometry_failures]

    def compute_energy(self, x, out):
        s, c = self.system, self.system.config
        wp.launch(energy.collision_energy_kernel, c.max_blocks,
                  inputs=[x, self.contact_counter, self.block_types, self.block_indices,
                          c.coll_stiffness, c.d_hat, c.ee_classify_thres, self.d, out]+extra(self), device=s.device)

    def compute_diff(self, x, coefficient, grad, diagonal):
        s, c = self.system, self.system.config
        wp.launch(energy.collision_diff_kernel, c.max_blocks,
                  inputs=[x, self.contact_counter, self.block_types, self.block_indices,
                          c.coll_stiffness, c.d_hat, self.d, coefficient, self.dd_dx, grad, diagonal]+extra(self), device=s.device)

    def compute_hess_dx(self, x, dx, out):
        s, c = self.system, self.system.config
        wp.launch(energy.collision_hess_dx_kernel, c.max_blocks,
                  inputs=[self.contact_counter, self.block_indices, self.d, c.coll_stiffness,
                          c.d_hat, self.dd_dx, dx, out]+extra(self), device=s.device)

    def compute_ccd(self, x, direction, step):
        s, c = self.system, self.system.config
        wp.launch(ccd.accd_kernel, c.max_blocks,
                  inputs=[self.contact_counter, x, direction, self.block_types, self.block_indices,
                          c.ccd_slackness, c.ccd_thickness, c.ccd_max_iters, c.ee_classify_thres, step]+extra(self), device=s.device)

    bound = []
    for key, calculator in system.energy_calcs.items():
        if key.__name__ not in ("CollisionEnergyCalculator", "CollisionBvhEnergyCalculator"):
            continue
        for name, method in (("compute_energy", compute_energy), ("compute_diff", compute_diff),
                             ("compute_hess_dx", compute_hess_dx), ("ccd", compute_ccd)):
            setattr(calculator, name, MethodType(method, calculator))
        bound.append(key.__name__)
    if not bound:
        raise ValueError("未找到完整接触列表碰撞计算器")
    Path(__file__).with_name("preserved_install.json").write_text(json.dumps(dict(bound_calculators=bound,
        scope="全部原固定接触保留原FP64毫米几何；包含自由点的接触沿用旧核体；检测列表不删减"),ensure_ascii=False,indent=2),encoding="utf-8")
