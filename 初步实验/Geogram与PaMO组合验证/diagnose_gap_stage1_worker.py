"""同一窄缝输入的两分辨率、两偏移第一阶段诊断，不运行简化或投影。"""

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
    check = json.loads(subprocess.run([checker, str(args.inputs.parent / config["normalized_source"]["file"])],
                                     check=True, text=True, capture_output=True).stdout)
    if not check["embedded_closed"]:
        raise ValueError("第一阶段实际场源不合法")
    args.output.mkdir(exist_ok=False)
    report = {"生成时间": datetime.now(timezone(timedelta(hours=8))).isoformat(),
              "修改时间及修改内容": "首次生成，两次SDF、四次第一阶段等值面生成",
              "文档概述": "同一源两分辨率与两偏移，不运行简化或投影，不产生发布",
              "索引目录": ["rows"], "inputs_sha256": sha(args.inputs), "rows": [], "chain": chain,
              "source_components": len(source.split(only_watertight=False)), "source_euler": int(source.euler_number),
              "full_PaMO_calls": 0, "SDF_calls": 2, "stage1_mesh_calls": 4}
    for resolution in (128, 256):
        # 同一分辨率仅求一次SDF，两偏移共用同一实际场，隔离偏移的作用。
        field = pamo.torchcumesh2sdf.get_sdf(torch.from_numpy(normalized).cuda(), resolution, model.band)
        torch.cuda.synchronize()
        if not torch.isfinite(field).all().item():
            raise ValueError("第一阶段场非有限")
        np.savez_compressed(args.output / f"{resolution}-实际未偏移GPU场.npz", field=field.cpu().numpy())
        for offset in (.9, 0.):
            vertices, triangles = model.vol2mesh(field - offset / resolution, return_quads=False)
            v, f = vertices.cpu().numpy(), triangles.cpu().numpy()
            # 沿作者逆变换及FP32中心化输出，再以FP64加回本批计算原点。
            v = (((v * resolution + .5) / (resolution + 1) * model.margin - model.band) * maximum + minimum)
            v = np.asarray(v, np.float32) + mean
            mesh = trimesh.Trimesh(np.asarray(v, np.float64) + origin, f, process=False)
            path = args.output / f"{resolution}-偏移{offset}-实际第一阶段.obj"
            save_obj(path, mesh)
            embedding = json.loads(subprocess.run([checker, str(path)], check=True, text=True, capture_output=True).stdout)
            report["rows"].append({"R": resolution, "offset": offset, "file": path.name, "sha256": sha(path),
                                   "components": len(mesh.split(only_watertight=False)), "euler": int(mesh.euler_number),
                                   "vertices": len(mesh.vertices), "faces": len(mesh.faces), "embedding": embedding})
    (args.output / "01-窄缝第一阶段四配置诊断.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), "utf8")
    print([(r["R"], r["offset"], r["components"], r["euler"], r["embedding"]["embedded_closed"]) for r in report["rows"]], flush=True)


if __name__ == "__main__":
    main()
