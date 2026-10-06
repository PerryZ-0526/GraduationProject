"""仅替换PaMO阶段一的SDF符号，诊断双壳是否由符号缺失造成。"""

import argparse
import json
from pathlib import Path

import numpy as np
import torch
import torchcumesh2sdf
import trimesh
from pamo import PaMO


def occupancy_mask(source, method, vertices, faces):
    triangles, minimum, extent, center = method.preprocess_mesh(
        vertices, faces, method.band, method.margin
    )
    pitch = float(np.max(source.extents)) / method.R
    voxels = source.voxelized(pitch).fill()
    axes = [
        (((np.arange(method.R) + 0.5) / method.R * method.margin - method.band)
         * extent + minimum[axis] + center[axis])
        for axis in range(3)
    ]
    yy, zz = np.meshgrid(axes[1], axes[2], indexing="ij")
    mask = np.empty((method.R, method.R, method.R), dtype=bool)
    for x_index, x_value in enumerate(axes[0]):
        points = np.column_stack((
            np.full(yy.size, x_value), yy.ravel(), zz.ravel()
        ))
        mask[x_index] = voxels.is_filled(points).reshape(method.R, method.R)
    return mask, pitch, int(voxels.matrix.sum())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=False)

    source = trimesh.load(args.input, force="mesh", process=False)
    method = PaMO(source, use_stage1=True, use_stage3=True)
    vertices = torch.from_numpy(np.asarray(source.vertices)).float().cuda()
    faces = torch.from_numpy(np.asarray(source.faces)).int().cuda()
    mask, pitch, voxel_count = occupancy_mask(source, method, vertices, faces)
    print("independent_occupied_grid_points", int(mask.sum()), flush=True)
    original_get_sdf = torchcumesh2sdf.get_sdf
    original_remesh = method.remesh
    diagnostics = {
        "input": args.input.name,
        "resolution": method.R,
        "voxel_pitch_mm": pitch,
        "independent_filled_voxels": voxel_count,
        "occupied_pamo_grid_points": int(mask.sum()),
        "interpretation": "独立体素填充仅供归因，不能充当连续几何或输入合法性证书",
    }

    def signed_get_sdf(tris, resolution, band):
        field = original_get_sdf(tris, resolution, band)
        diagnostics["original_negative_voxels"] = int((field < 0).sum().item())
        interior = torch.from_numpy(mask).to(field.device)
        replaced = torch.where(interior, -torch.abs(field), torch.abs(field))
        diagnostics["replaced_negative_voxels"] = int((replaced < 0).sum().item())
        return replaced

    def capture_remesh(tris, tris_min, tris_max, tris_mean):
        stage_vertices, stage_faces = original_remesh(tris, tris_min, tris_max, tris_mean)
        stage_mesh = trimesh.Trimesh(
            vertices=stage_vertices.cpu().numpy() + tris_mean,
            faces=stage_faces.cpu().numpy(), process=False,
        )
        stage_mesh.export(args.output_dir / "stage1.obj")
        return stage_vertices, stage_faces

    torchcumesh2sdf.get_sdf = signed_get_sdf
    method.remesh = capture_remesh
    try:
        output_vertices, output_faces = method.run(
            vertices, faces, ratio=1.0, min_verts=0
        )
    finally:
        torchcumesh2sdf.get_sdf = original_get_sdf
    trimesh.Trimesh(
        vertices=output_vertices, faces=output_faces, process=False
    ).export(args.output_dir / "final.obj")
    (args.output_dir / "diagnostics.json").write_text(
        json.dumps(diagnostics, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(diagnostics, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
