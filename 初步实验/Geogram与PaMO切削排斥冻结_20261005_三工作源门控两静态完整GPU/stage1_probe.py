"""记录PaMO原阶段一与阶段二的网格，用于固定输入的归因探查。"""

import argparse
from pathlib import Path

import numpy as np
import torch
import trimesh
from pamo import PaMO


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--resolution", type=int, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=False)

    source = trimesh.load(args.input, force="mesh", process=False)
    method = PaMO(source, use_stage1=True, use_stage3=False)
    method.R = args.resolution
    method.band = 3 / args.resolution
    method.margin = method.band * 2 + 1
    original_remesh = method.remesh

    def capture_remesh(tris, tris_min, tris_max, tris_mean):
        vertices, faces = original_remesh(tris, tris_min, tris_max, tris_mean)
        # 阶段一内部使用中心化坐标，导出时恢复原始骨坐标。
        mesh = trimesh.Trimesh(
            vertices=vertices.cpu().numpy() + tris_mean,
            faces=faces.cpu().numpy(),
            process=False,
        )
        mesh.export(args.output_dir / "stage1.obj")
        print("stage1_vertices", len(mesh.vertices), "stage1_faces", len(mesh.faces), flush=True)
        return vertices, faces

    method.remesh = capture_remesh
    vertices, faces = method.run(
        torch.from_numpy(np.asarray(source.vertices)).float().cuda(),
        torch.from_numpy(np.asarray(source.faces)).int().cuda(),
        ratio=1.0,
        min_verts=0,
    )
    mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    mesh.export(args.output_dir / "stage2.obj")
    print("stage2_vertices", len(mesh.vertices), "stage2_faces", len(mesh.faces), flush=True)


if __name__ == "__main__":
    main()
