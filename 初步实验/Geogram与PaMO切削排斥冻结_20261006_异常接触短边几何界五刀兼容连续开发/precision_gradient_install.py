"""在分类距离精度副本上替换梯度，保留作者Hessian组装与边边计算。"""
import hashlib
import importlib
import importlib.util
import json
from pathlib import Path
import sys
import warp as wp
from precision_collision_install import install_precision_collision


def install_precision_gradient():
    base = install_precision_collision()
    energy = importlib.import_module("pamo_safe_project.energy")
    original = sys.modules["pamo_safe_project.kernels.energy_kernels.precision_collision_energy"]
    source = Path(original.__file__).read_text(encoding="utf-8")
    marker = "\n@wp."
    prefix, body = source.split(marker, 1)
    modified = prefix + "\nfrom robust_pt_gradient_gpu import robust_pt_gradient_array as pt_pair_distance_grad, robust_pt_gradient_struct as pt_pair_distance_grad_struct\n" + marker + body
    target = Path(__file__).with_name("author_precision_snapshots") / "collision_gradient_precision.py"
    target.write_text(modified, encoding="utf-8")
    identity = "pamo_safe_project.kernels.energy_kernels.precision_gradient_collision_energy"
    spec = importlib.util.spec_from_file_location(identity, target)
    clone = importlib.util.module_from_spec(spec)
    sys.modules[identity] = clone
    spec.loader.exec_module(clone)
    replaced = []
    for key, value in vars(original).items():
        if isinstance(value, wp.Kernel) and getattr(energy, key, None) is value:
            setattr(energy, key, getattr(clone, key))
            replaced.append(key)
    required = {"collision_diff_kernel", "collision_hess_dx_kernel"}
    if not required.issubset(replaced):
        raise ValueError("梯度替换未覆盖导数与Hessian向量乘入口")
    record = {"classification_distance": base, "replaced_kernels": replaced,
              "isolated_sha256": hashlib.sha256(modified.encode()).hexdigest(),
              "scope": "点三角形梯度使用FP64最近点权重；原Hessian组装与边边计算不变，未证明整体Hessian精度"}
    Path(__file__).with_name("gradient_install.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return record
