"""窄缝第二刀四种归一化表示的实际CUDA预处理诊断，不求SDF或完整PaMO。"""

import argparse
import hashlib
import importlib.util
import inspect
import json
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone, timedelta

import numpy as np
import torch
import trimesh
from single_round_normalization import normalize_initial_once
from normalized_sdf_chain import canonical_normalized_chain


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save_obj(path, mesh):
    # 17位数字绑定实际阶段输出，不作额外焊接或拓扑修补。
    with path.open("w", encoding="utf8") as stream:
        for point in mesh.vertices:
            stream.write("v " + " ".join(format(float(x), ".17g") for x in point) + "\n")
        for face in mesh.faces:
            stream.write("f " + " ".join(str(int(x) + 1) for x in face) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    config = json.loads(args.inputs.read_text("utf8"))
    for name in ("source", "normalized_source"):
        if sha(args.inputs.parent / config[name]["file"]) != config[name]["sha256"]:
            raise ValueError("实际第一阶段输入摘要不同")
    extension = config["sorted_extension"]
    if sha(extension["extension"]) != extension["extension_sha256"]:
        raise ValueError("排序扩展改变")
    spec = importlib.util.spec_from_file_location(extension["module"], extension["extension"])
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sys.modules["pamo._C"] = module
    import pamo
    if sha(inspect.getfile(pamo.PaMO)) != "0d7781dd3b3bb9579e966dc8ddc016a4b1c0036b8386747511ba092c9591ee7a":
        raise ValueError("作者源码改变")
    if sha(pamo.torchcumesh2sdf.__file__) != "c0836ff8d36fe5c9e2fca8f27e9a341578aa3d716dfb1d0563784710717353ad":
        raise ValueError("SDF扩展改变")
    checker = "/root/autodl-tmp/graduation_project/exact_mesh_audit_20261004_0646"
    if sha(checker) != "0af22fcb7cad4de31524cd09d5b143a3716f53c81d5c271a218307da05adcdd3":
        raise ValueError("精确检查器改变")
    if sha(config["pair_checker"]) != config["pair_checker_sha256"]:
        raise ValueError("定位器摘要改变")
    source = trimesh.load(args.inputs.parent / config["source"]["file"], force="mesh", process=False)
    original_normalized = trimesh.load(args.inputs.parent / config["normalized_source"]["file"], force="mesh", process=False)
    local = source.copy()
    origin = np.asarray(config["origin_mm"], np.float64)
    local.vertices = np.asarray(source.vertices, np.float64) - origin
    points = torch.from_numpy(np.asarray(local.vertices, np.float32)).cuda()
    faces = torch.from_numpy(np.asarray(local.faces, np.int32)).cuda()
    model = pamo.PaMO(local, use_stage1=True, use_stage3=False)
    _, minimum, maximum, mean = model.preprocess_mesh(points, faces, model.band, model.margin)
    normalized = normalize_initial_once(points.cpu().numpy(), faces.cpu().numpy(), mean, minimum, maximum, model.band, model.margin)
    _, _, normalized, chain = canonical_normalized_chain(normalized)
    if not np.array_equal(normalized.astype(np.float64), original_normalized.vertices[original_normalized.faces]):
        raise ValueError("重建归一化场源与原完整运行工作源不逐位相同")
    args.output.mkdir(exist_ok=False)
    p32 = points.cpu().numpy()
    centered32 = (points - torch.from_numpy(mean).to(points.device)).cpu().numpy()
    indices = faces.cpu().numpy()
    mean64, min64 = np.asarray(mean, np.float64), np.asarray(minimum, np.float64)
    def affine(coordinates):
        return ((np.asarray(coordinates, np.float64) - mean64 - min64) / float(maximum) + float(model.band)) / float(model.margin)
    choices = [
        ("01-初始CUDA源单次FP32控制", normalized, None),
        ("02-物理FP64源归一化后单次FP32", np.asarray(affine(local.vertices)[indices], np.float32), None),
        ("03-碰撞源FP64中间值后单次FP32", np.asarray(((np.asarray(centered32, np.float64) - min64) / float(maximum) + float(model.band)) / float(model.margin), np.float32)[indices], None),
        ("04-初始CUDA源全FP64归一化几何控制", affine(p32)[indices], "geometry_only_not_supported_original_SDF_input")]
    report = {"生成时间": datetime.now(timezone(timedelta(hours=8))).isoformat(),
              "修改时间及修改内容": "首次生成，固定源/原点/作者参数的四表示完整检查",
              "文档概述": "实际CUDA预处理，不求SDF，不运行完整算法，不改变碰撞源",
              "索引目录": ["parameters", "rows"], "inputs_sha256": sha(args.inputs),
              "parameters": {"origin_mm": origin.tolist(), "mean_mm": mean.tolist(), "minimum_mm": minimum.tolist(),
                             "maximum_span_mm": float(maximum), "band": model.band, "margin": model.margin},
              "full_PaMO_calls": 0, "SDF_calls": 0, "rows": []}
    for name, array, scope in choices:
        vertices, triangles, array, details = canonical_normalized_chain(array)
        mesh = trimesh.Trimesh(vertices, triangles, process=False)
        path = args.output / (name + ".obj")
        save_obj(path, mesh)
        checked = subprocess.run([config["pair_checker"], str(path)], check=True, text=True, capture_output=True)
        embedding = json.loads(checked.stdout)
        report["rows"].append({"variant": name, "file": path.name, "sha256": sha(path), "chain": details,
                               "scope": scope or "candidate_FP32_normalized_source", "embedding": embedding,
                               "components": len(mesh.split(only_watertight=False)), "euler": int(mesh.euler_number)})
    if report["rows"][0]["embedding"]["self_intersection_pairs"] != config["expected_control_intersections"]:
        raise ValueError("原控制归一化自交与完整运行不一致")
    if sha(config["pair_checker"]) != config["pair_checker_sha256"]:
        raise ValueError("定位器摘要改变")
    for name, vertices in [("05-实际CUDA初始编码源.obj", p32), ("06-实际CUDA再中心化碰撞源.obj", centered32)]:
        path = args.output / name
        save_obj(path, trimesh.Trimesh(vertices, indices, process=False))
    (args.output / "07-第二刀四归一化表示实际预处理诊断.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), "utf8")
    print([(r["variant"],r["embedding"]["embedded_closed"],r["embedding"]["self_intersection_pairs"]) for r in report["rows"]], flush=True)


if __name__ == "__main__":
    main()
