"""用实体角和射线包含在冻结点上交叉核查清理版输入。"""

import argparse
import json
from pathlib import Path

import numpy as np
import trimesh


def winding_numbers(mesh, points):
    triangles = np.asarray(mesh.vertices, dtype=np.float64)[mesh.faces]
    values = []
    for point in points:
        vectors = triangles - point
        lengths = np.linalg.norm(vectors, axis=2)
        numerator = np.einsum("ij,ij->i", vectors[:, 0],
                               np.cross(vectors[:, 1], vectors[:, 2]))
        denominator = (
            lengths[:, 0] * lengths[:, 1] * lengths[:, 2]
            + np.einsum("ij,ij->i", vectors[:, 0], vectors[:, 1]) * lengths[:, 2]
            + np.einsum("ij,ij->i", vectors[:, 1], vectors[:, 2]) * lengths[:, 0]
            + np.einsum("ij,ij->i", vectors[:, 2], vectors[:, 0]) * lengths[:, 1]
        )
        values.append(np.sum(2 * np.arctan2(numerator, denominator)) / (4 * np.pi))
    return np.asarray(values)


def audit(path):
    mesh = trimesh.load(path, force="mesh", process=False)
    grid = np.asarray(np.meshgrid([-2.2, -1.5, 0, 1.5, 2.2],
                                  [-2.2, -1.5, 0, 1.5, 2.2],
                                  [-0.8, -0.5, 0.0], indexing="ij"))
    points = grid.reshape(3, -1).T
    winding = winding_numbers(mesh, points)
    winding_inside = np.abs(winding) > 0.5
    ray_inside = mesh.contains(points)
    return {
        "input": str(path),
        "points": len(points),
        "winding_inside": int(winding_inside.sum()),
        "ray_inside": int(ray_inside.sum()),
        "classification_disagreements": int(np.count_nonzero(winding_inside != ray_inside)),
        "interior_core_disagreements": int(np.count_nonzero(
            (winding_inside != ray_inside) & (np.abs(points[:, 0]) <= 1.5)
            & (np.abs(points[:, 1]) <= 1.5) & (points[:, 2] <= -0.5))),
        "watertight": bool(mesh.is_watertight),
        "winding_consistent": bool(mesh.is_winding_consistent),
        "signed_volume_mm3": float(mesh.volume),
        "interpretation": "有限离散点交叉核查，不能证明整张网格无几何自交或符号算法对任意骨面可靠",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.write_text(json.dumps([audit(path) for path in args.inputs],
                                     ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
