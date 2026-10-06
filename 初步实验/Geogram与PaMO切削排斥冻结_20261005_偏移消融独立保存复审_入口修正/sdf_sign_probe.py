"""按PaMO阶段一的原始归一化流程统计有符号距离场的符号。"""

import argparse
import json
from pathlib import Path

import numpy as np
import torch
import torchcumesh2sdf
import trimesh
from pamo import PaMO


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--resolution", type=int, default=256)
    args = parser.parse_args()

    source = trimesh.load(args.input, force="mesh", process=False)
    method = PaMO(source, use_stage1=True, use_stage3=False)
    method.R = args.resolution
    method.band = 3 / args.resolution
    method.margin = method.band * 2 + 1
    vertices = torch.from_numpy(np.asarray(source.vertices)).float().cuda()
    faces = torch.from_numpy(np.asarray(source.faces)).int().cuda()
    triangles, _, _, _ = method.preprocess_mesh(
        vertices, faces, method.band, method.margin
    )
    field = torchcumesh2sdf.get_sdf(
        torch.tensor(triangles, dtype=torch.float32, device="cuda"),
        method.R,
        method.band,
    )
    offset_field = field - 0.9 / method.R
    result = {
        "resolution": method.R,
        "input": args.input.name,
        "shape": list(field.shape),
        "sdf_min": float(field.min().item()),
        "sdf_max": float(field.max().item()),
        "sdf_negative_voxels": int((field < 0).sum().item()),
        "offset_negative_voxels": int((offset_field < 0).sum().item()),
        "total_voxels": int(field.numel()),
    }
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
