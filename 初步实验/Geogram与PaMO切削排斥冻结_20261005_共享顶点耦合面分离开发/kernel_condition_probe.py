"""按作者 FP32 预处理复核开放栅格边上的单面射线相交条件。"""

import argparse
import json
from pathlib import Path

import numpy as np
import trimesh


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--classification", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    source = trimesh.load(args.input, force="mesh", process=False)
    evidence = json.loads(args.classification.read_text(encoding="utf-8"))
    crossing = evidence["crossings"][0]
    face_id = crossing["source_triangle_hits"][0]["face_id"]
    triangles = np.asarray(source.vertices, dtype=np.float32)[source.faces]
    mean = triangles.mean(axis=1).mean(axis=0)
    centered = triangles - mean
    minimum = centered.min(axis=(0, 1))
    shifted = centered - minimum
    extent = shifted.max()
    resolution = 256
    band = 3 / resolution
    margin = 2 * band + 1
    normalized = ((shifted / extent + band) / margin).astype(np.float32)
    origin_mm = np.asarray(crossing["from_mm"], dtype=np.float64)
    origin_ijk = np.rint(((origin_mm - mean - minimum) / extent + band)
                          / margin * resolution - 0.5).astype(int)
    origin = ((origin_ijk + 0.5) / resolution).astype(np.float32)
    vertices = normalized[face_id]
    v1, v2, v3 = vertices
    edge1 = np.asarray(v2 - v1, dtype=np.float32)
    edge2 = np.asarray(v3 - v1, dtype=np.float32)
    ray_origin = np.asarray(origin - v1, dtype=np.float32)
    direction = np.asarray([0, 0, 1], dtype=np.float32)
    cr = np.cross(direction, edge2)
    determinant = np.dot(cr, edge1)
    u = np.dot(ray_origin, cr) / determinant
    scr = np.cross(ray_origin, edge1)
    v = np.dot(direction, scr) / determinant
    t = np.dot(edge2, scr) / determinant
    epsilon = np.finfo(np.float32).eps
    hit = bool(abs(determinant) > 1e-12 and t >= 0 and u >= -epsilon
               and v >= -epsilon and u + v <= 1 + epsilon)
    report = {
        "input": args.input.name,
        "face_id": face_id,
        "origin_grid": origin_ijk.tolist(),
        "origin_normalized": origin.tolist(),
        "triangle_normalized_fp32": vertices.tolist(),
        "determinant": float(determinant),
        "u": float(u),
        "v": float(v),
        "t": float(t),
        "ray_hit_under_source_predicate": hit,
        "one_over_resolution": 1 / resolution,
        "interpretation": "CPU FP32 表达式对拍，不能逐位替代 CUDA 运算或证明面已被枚举",
    }
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
