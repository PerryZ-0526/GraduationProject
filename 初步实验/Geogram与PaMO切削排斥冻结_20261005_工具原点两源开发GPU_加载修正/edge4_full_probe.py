"""在隔离的近边容差变体下捕获 PaMO 完整三阶段网格。"""

import argparse
import json
from pathlib import Path

import numpy as np
import pamo_safe_project
import torch
import torchcumesh2sdf
import trimesh
from pamo import PaMO


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=False)
    source = trimesh.load(args.input, force="mesh", process=False)
    method = PaMO(source, use_stage1=True, use_stage3=True)
    vertices = torch.from_numpy(np.asarray(source.vertices)).float().cuda()
    faces = torch.from_numpy(np.asarray(source.faces)).int().cuda()
    original_sdf = torchcumesh2sdf.get_sdf
    original_remesh = method.remesh
    original_project = pamo_safe_project.process
    diagnostics = {"input": args.input.name,
                   "extension": torchcumesh2sdf.__file__, "ratio": 1.0}

    def capture_sdf(triangles, resolution, band):
        field = original_sdf(triangles, resolution, band)
        diagnostics["negative_sdf_voxels"] = int((field < 0).sum().item())
        return field

    def capture_remesh(triangles, minimum, extent, center):
        stage_vertices, stage_faces = original_remesh(
            triangles, minimum, extent, center
        )
        # 阶段一使用中心化坐标，导出时恢复原始骨坐标。
        trimesh.Trimesh(
            vertices=stage_vertices.cpu().numpy() + center,
            faces=stage_faces.cpu().numpy(), process=False,
        ).export(args.output_dir / "stage1.obj")
        return stage_vertices, stage_faces

    def capture_project(source_vertices, source_faces, stage_vertices,
                        stage_faces, *positional, **keywords):
        # 阶段二输出直接取作者投影函数的输入，不改变其后续调用。
        trimesh.Trimesh(
            vertices=stage_vertices, faces=stage_faces, process=False,
        ).export(args.output_dir / "stage2.obj")
        return original_project(source_vertices, source_faces, stage_vertices,
                                stage_faces, *positional, **keywords)

    torchcumesh2sdf.get_sdf = capture_sdf
    method.remesh = capture_remesh
    pamo_safe_project.process = capture_project
    try:
        result_vertices, result_faces = method.run(
            vertices, faces, ratio=1.0, min_verts=0
        )
    finally:
        torchcumesh2sdf.get_sdf = original_sdf
        pamo_safe_project.process = original_project
    trimesh.Trimesh(
        vertices=result_vertices, faces=result_faces, process=False,
    ).export(args.output_dir / "final.obj")
    (args.output_dir / "diagnostics.json").write_text(
        json.dumps(diagnostics, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(diagnostics, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
