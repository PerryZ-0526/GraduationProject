"""在隔离进程仅改变阶段一符号场偏移幅度，保留完整阶段观测。"""

import hashlib
import inspect
import json
from pathlib import Path
import runpy
import sys

import numpy as np
import torch
import pamo_safe_project
import trimesh

from locality_masks import save_obj_fp64


output = Path(sys.argv[sys.argv.index("--output") + 1])
observations = output.parent / "stage_observations"
observations.mkdir()
# 只在当前隔离进程加载实验扩展，作者已安装扩展保持原样。
import importlib.util
extension_info = json.loads(Path(__file__).with_name("order_extension.json").read_text("utf8"))
assert hashlib.sha256(Path(extension_info["extension"]).read_bytes()).hexdigest() == extension_info["extension_sha256"]
spec = importlib.util.spec_from_file_location(extension_info["module"], extension_info["extension"])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
sys.modules["pamo._C"] = module
import pamo
pamo._C = module
assert hashlib.sha256(Path(inspect.getfile(pamo.PaMO)).read_bytes()).hexdigest() == "0d7781dd3b3bb9579e966dc8ddc016a4b1c0036b8386747511ba092c9591ee7a"
record = {"role": "observational_full_three_stages_extra_readback_not_timing", "tensors": {}, "extension": extension_info}


def digest_tensor(name, tensor):
    # 显式读回用于摘要定位，不修改张量；同步开销不用于性能结论。
    array = tensor.detach().cpu().numpy()
    record["tensors"][name] = {"sha256": hashlib.sha256(array.tobytes()).hexdigest(),
                                "shape": list(array.shape), "finite": bool(np.isfinite(array).all())}


original_sdf = pamo.torchcumesh2sdf.get_sdf


def observed_sdf(tris, *args, **kwargs):
    digest_tensor("normalized_input_triangles", tris)
    result = original_sdf(tris, *args, **kwargs)
    digest_tensor("stage1_sdf", result)
    return result


original_preprocess = pamo.PaMO.preprocess_mesh


def observed_preprocess(self, *args, **kwargs):
    result = original_preprocess(self, *args, **kwargs)
    self.observation_mean = result[3].copy()
    return result


offset_factor = extension_info["sdf_offset_factor"]
assert offset_factor in (0.0, 0.45, 0.9)
record["sdf_offset_factor"] = offset_factor


def bias_remesh(self, tris, tris_min, tris_max, tris_mean):
    # 原样复用作者阶段一计算次序，仅替换常数偏移幅度；不修改作者安装。
    d = pamo.torchcumesh2sdf.get_sdf(tris, self.R, self.band)
    d = d - offset_factor / self.R
    v, f = self.vol2mesh(d, return_quads=False)
    v, f = v.cpu().numpy(), f.cpu().numpy()
    v = (((v * self.R + 0.5) / (self.R + 1) * self.margin - self.band) * tris_max + tris_min)
    v = torch.from_numpy(v).float().cuda()
    f = torch.from_numpy(f).int().cuda()
    return v, f


original_remesh = bias_remesh


def observed_remesh(self, *args, **kwargs):
    verts, faces = original_remesh(self, *args, **kwargs)
    # 恢复同一个作者中心偏移，便于三个阶段使用同一坐标比较。
    mesh = trimesh.Trimesh(vertices=verts.detach().cpu().numpy() + self.observation_mean,
                           faces=faces.detach().cpu().numpy(), process=False)
    save_obj_fp64(mesh, observations / "stage1.obj")
    return verts, faces


original_process = pamo_safe_project.process


def observed_process(gt_vertices, gt_faces, vertices, faces, *args, **kwargs):
    save_obj_fp64(trimesh.Trimesh(vertices=vertices, faces=faces, process=False), observations / "stage2.obj")
    result = original_process(gt_vertices, gt_faces, vertices, faces, *args, **kwargs)
    save_obj_fp64(trimesh.Trimesh(vertices=result[0], faces=result[1], process=False), observations / "stage3.obj")
    (observations / "observation.json").write_text(json.dumps(record, indent=2), encoding="utf8")
    return result


original_init = pamo.PaMO.__init__


def observed_init(self, *args, **kwargs):
    original_init(self, *args, **kwargs)
    original_function = self.func
    record["simplification_calls"] = []
    iterations = observations / "iterations"
    iterations.mkdir()

    class ObservedFunction:
        @staticmethod
        def apply(*inputs):
            index = len(record["simplification_calls"])
            # 只读取有定义的有效输入，初始空撤销数组不引入额外数值。
            before = {}
            for name, tensor in zip(("vertices", "faces", "undo"), inputs[:3]):
                array = tensor.detach().cpu().numpy()
                before[name] = {"sha256": hashlib.sha256(array.tobytes()).hexdigest(), "shape": list(array.shape)}
            result = original_function.apply(*inputs)
            verts, faces, occupied, mapping, undo = result
            # 严格使用作者下一步的筛选与索引方式，只在副本上构造观测网格。
            compact = verts[occupied.view(-1).bool()].detach().cpu().numpy()
            live_faces = faces[faces[:, 0] >= 0]
            mapped = mapping[live_faces.long()].view(live_faces.shape).detach().cpu().numpy()
            after = {name: {"sha256": hashlib.sha256(array.tobytes()).hexdigest(), "shape": list(array.shape)}
                     for name, array in (("compacted_vertices", compact), ("mapped_faces", mapped))}
            name = f"iteration_{index:03d}.obj"
            save_obj_fp64(trimesh.Trimesh(vertices=compact + self.observation_mean, faces=mapped, process=False), iterations / name)
            record["simplification_calls"].append({"index": index, "input": before, "output": after,
                  "num_faces_before": int(inputs[1].shape[0]), "num_faces_after": int(mapped.shape[0]),
                  "n_verts_undo": int(inputs[3]), "threshold": float(inputs[5]), "is_stuck": int(inputs[6]),
                  "init": bool(inputs[7]), "mesh_file": name})
            # 原始返回对象完整交还作者循环，不使用观测副本作为算法状态。
            return result

    self.func = ObservedFunction


pamo.PaMO.__init__ = observed_init
pamo.torchcumesh2sdf.get_sdf = observed_sdf
pamo.PaMO.preprocess_mesh = observed_preprocess
pamo.PaMO.remesh = observed_remesh
pamo_safe_project.process = observed_process
runpy.run_path(str(Path(__file__).with_name("original_capacity_launcher.py")), run_name="__main__")
