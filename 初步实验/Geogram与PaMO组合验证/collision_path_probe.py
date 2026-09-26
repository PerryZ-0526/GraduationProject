"""检查 PaMO 栅格碰撞边是否把已知内部点与外部连通。"""

import argparse
from collections import deque
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
    points = torch.from_numpy(np.asarray(source.vertices)).float().cuda()
    faces = torch.from_numpy(np.asarray(source.faces)).int().cuda()
    triangles, minimum, extent, center = method.preprocess_mesh(
        points, faces, method.band, method.margin
    )
    collision = torchcumesh2sdf.get_collide(
        torch.tensor(triangles, dtype=torch.float32, device="cuda"),
        method.R, method.band,
    ).cpu().numpy()
    axes = [
        (((np.arange(method.R) + 0.5) / method.R * method.margin - method.band)
         * extent + minimum[axis] + center[axis])
        for axis in range(3)
    ]
    seed = tuple(int(np.argmin(np.abs(axis - value)))
                 for axis, value in zip(axes, (0.0, 0.0, -0.5)))
    resolution = method.R
    stride_x = resolution * resolution
    seed_index = seed[0] * stride_x + seed[1] * resolution + seed[2]
    parent = np.full(resolution**3, -1, dtype=np.int32)
    parent[seed_index] = seed_index
    queue = deque([seed_index])
    reached = None
    while queue:
        current = queue.popleft()
        x, remainder = divmod(current, stride_x)
        y, z = divmod(remainder, resolution)
        if 0 in (x, y, z) or resolution - 1 in (x, y, z):
            reached = current
            break
        neighbors = (
            (current + stride_x, not collision[x, y, z, 0]),
            (current - stride_x, not collision[x - 1, y, z, 0]),
            (current + resolution, not collision[x, y, z, 1]),
            (current - resolution, not collision[x, y - 1, z, 1]),
            (current + 1, not collision[x, y, z, 2]),
            (current - 1, not collision[x, y, z - 1, 2]),
        )
        for neighbor, open_edge in neighbors:
            if open_edge and parent[neighbor] < 0:
                parent[neighbor] = current
                queue.append(neighbor)
    path = []
    if reached is not None:
        current = reached
        while current != seed_index:
            path.append(current)
            current = int(parent[current])
        path.append(seed_index)
        path.reverse()
    path_points = []
    for index in path:
        x, remainder = divmod(index, stride_x)
        y, z = divmod(remainder, resolution)
        path_points.append([float(axes[0][x]), float(axes[1][y]), float(axes[2][z])])
    report = {
        "input": args.input.name,
        "resolution": resolution,
        "seed_grid": seed,
        "seed_physical_mm": [float(axes[i][seed[i]]) for i in range(3)],
        "visited_grid_points": int(np.count_nonzero(parent >= 0)),
        "reached_boundary": reached is not None,
        "path_grid_edges": max(0, len(path) - 1),
        "path_points_mm": path_points,
        "interpretation": "碰撞边连通路径诊断；点包含由本机独立核查",
    }
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
