"""调用隔离编译的碰撞栅格并读取两条固定边的标志。"""

import argparse
from pathlib import Path

import numpy as np
import torch
import torchcumesh2sdf
import trimesh
from pamo import PaMO


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--grid", required=True, nargs=3, type=int)
    args = parser.parse_args()
    source = trimesh.load(args.input, force="mesh", process=False)
    method = PaMO(source, use_stage1=True, use_stage3=False)
    vertices = torch.from_numpy(np.asarray(source.vertices)).float().cuda()
    faces = torch.from_numpy(np.asarray(source.faces)).int().cuda()
    triangles, _, _, _ = method.preprocess_mesh(
        vertices, faces, method.band, method.margin
    )
    print("EXTENSION", torchcumesh2sdf.__file__, flush=True)
    collision = torchcumesh2sdf.get_collide(
        torch.tensor(triangles, dtype=torch.float32, device="cuda"),
        method.R, method.band,
    )
    x, y, z = args.grid
    print("GRID", x, y, z, flush=True)
    print("COLLISION_Z", bool(collision[x, y, z, 2].item()), flush=True)


if __name__ == "__main__":
    main()
