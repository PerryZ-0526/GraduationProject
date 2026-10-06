"""固定采样隔离容差变体的 SDF 节点，供本机独立包含审计。"""

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
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    source = trimesh.load(args.input, force="mesh", process=False)
    method = PaMO(source, use_stage1=True, use_stage3=False)
    vertices = torch.from_numpy(np.asarray(source.vertices)).float().cuda()
    faces = torch.from_numpy(np.asarray(source.faces)).int().cuda()
    triangles, minimum, extent, center = method.preprocess_mesh(
        vertices, faces, method.band, method.margin
    )
    field = torchcumesh2sdf.get_sdf(
        torch.tensor(triangles, dtype=torch.float32, device="cuda"),
        method.R, method.band,
    ).cpu().numpy()
    flat = field.ravel()
    rng = np.random.default_rng(20260927)
    groups = {
        "negative": np.flatnonzero(flat < 0),
        "positive": np.flatnonzero(flat > 0),
        "near_surface": np.flatnonzero(np.abs(flat) < 2 / method.R),
    }
    chosen = {name: rng.choice(indices, size=min(256, len(indices)), replace=False)
              for name, indices in groups.items()}
    axes = [
        (((np.arange(method.R) + 0.5) / method.R * method.margin - method.band)
         * extent + minimum[axis] + center[axis])
        for axis in range(3)
    ]
    samples = []
    for group, indices in chosen.items():
        for index in indices:
            x, y, z = np.unravel_index(int(index), field.shape)
            samples.append({
                "group": group,
                "grid": [int(x), int(y), int(z)],
                "point_mm": [float(axes[0][x]), float(axes[1][y]), float(axes[2][z])],
                "sdf": float(field[x, y, z]),
            })
    result = {
        "input": args.input.name,
        "resolution": method.R,
        "negative_voxels": int(np.count_nonzero(flat < 0)),
        "groups_available": {name: len(indices) for name, indices in groups.items()},
        "samples": samples,
    }
    args.output.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    print({"input": args.input.name,
           "negative_voxels": result["negative_voxels"],
           "sample_count": len(samples)}, flush=True)


if __name__ == "__main__":
    main()
