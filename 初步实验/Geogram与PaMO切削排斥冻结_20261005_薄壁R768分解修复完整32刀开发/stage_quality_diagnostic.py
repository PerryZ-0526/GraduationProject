"""对冻结网格逐面统计质量来源及空间位置。"""

import argparse
import json
from pathlib import Path

import numpy as np
import trimesh


def audit(path):
    mesh = trimesh.load(path, force="mesh", process=False)
    triangles = np.asarray(mesh.vertices, dtype=np.float64)[mesh.faces]
    sides = np.roll(triangles, 1, axis=1) - triangles
    lengths2 = np.sum(sides * sides, axis=2)
    cross = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    doubled_area = np.linalg.norm(cross, axis=1)
    quality = np.divide(2 * np.sqrt(3) * doubled_area, lengths2.sum(axis=1),
                        out=np.zeros(len(triangles)), where=lengths2.sum(axis=1) > 0)
    angles = []
    for corner in range(3):
        a = triangles[:, (corner + 1) % 3] - triangles[:, corner]
        b = triangles[:, (corner + 2) % 3] - triangles[:, corner]
        cosine = np.divide(np.sum(a * b, axis=1), np.linalg.norm(a, axis=1) * np.linalg.norm(b, axis=1),
                           out=np.ones(len(triangles)), where=(np.linalg.norm(a, axis=1) * np.linalg.norm(b, axis=1)) > 0)
        angles.append(np.degrees(np.arccos(np.clip(cosine, -1, 1))))
    minimum_angle = np.min(np.stack(angles, axis=1), axis=1)
    angle_bad = minimum_angle < 25
    quality_bad = quality < 0.4
    area_bad = doubled_area <= 2e-12
    bad = angle_bad | quality_bad | area_bad | ~np.isfinite(quality)
    normals = np.divide(cross, doubled_area[:, None], out=np.zeros_like(cross),
                        where=doubled_area[:, None] > 0)
    centers = triangles.mean(axis=1)
    # 以面法线区分顶底面和侧壁，斜面归入过渡区域。
    zones = {
        "up": normals[:, 2] > 0.8,
        "down": normals[:, 2] < -0.8,
        "side_or_transition": np.abs(normals[:, 2]) <= 0.8,
    }
    boundary_distance = np.minimum(2 - np.abs(centers[:, 0]), 2 - np.abs(centers[:, 1]))
    return {
        "path": str(path),
        "faces": len(triangles),
        "bad_faces": int(bad.sum()),
        "angle_only": int((angle_bad & ~quality_bad & ~area_bad).sum()),
        "quality_only": int((quality_bad & ~angle_bad & ~area_bad).sum()),
        "both_angle_quality": int((angle_bad & quality_bad).sum()),
        "area_bad": int(area_bad.sum()),
        "minimum_angle_deg": float(minimum_angle.min()),
        "minimum_q": float(quality.min()),
        "zones": {name: {"faces": int(mask.sum()), "bad_faces": int((bad & mask).sum())}
                  for name, mask in zones.items()},
        "bad_near_xy_border_0_1mm": int((bad & (boundary_distance < 0.1)).sum()),
        "bad_interior_xy": int((bad & (boundary_distance >= 0.1)).sum()),
        "bad_center_bbox_mm": [centers[bad].min(axis=0).tolist(), centers[bad].max(axis=0).tolist()] if bad.any() else None,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    rows = [audit(path) for path in args.paths]
    args.output.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
