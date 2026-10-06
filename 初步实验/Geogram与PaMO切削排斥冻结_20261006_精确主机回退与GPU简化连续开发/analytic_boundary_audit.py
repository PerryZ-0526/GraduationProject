"""独立核对箱体侧边的扫掠间隙及局部网格的解析场残差。"""

import argparse
import json
from pathlib import Path
import sys

import numpy as np
import trimesh


COMMON = Path(__file__).resolve().parents[1] / "共同运动记录与方法对照"
sys.path.insert(0, str(COMMON))
from motion_record import initial_field, load_document, motion_field, replay_case


def local_points(mesh, centers):
    vertices = np.asarray(mesh.vertices)
    triangles = vertices[np.asarray(mesh.faces)]
    centroids = triangles.mean(axis=1)
    mask = np.min(np.linalg.norm(centroids[:, None] - centers[None], axis=2), axis=1) < 0.12
    selected = triangles[mask]
    weights = np.array([[i / 4, j / 4, 1 - (i + j) / 4]
                        for i in range(5) for j in range(5 - i)])
    return np.einsum("sc,fcd->sfd", weights, selected).reshape(-1, 3), int(mask.sum())


def field_residual(points, case, replay):
    bounds = np.maximum.reduce((
        -points[:, 0] - 2, points[:, 0] - 2,
        -points[:, 1] - 2, points[:, 1] - 2,
        -0.9 - points[:, 2],
    ))
    swept = motion_field(points, replay)
    field = np.maximum.reduce((initial_field(points, case), -swept, bounds))
    return {"max_abs_field_mm": float(np.max(np.abs(field))),
            "p95_abs_field_mm": float(np.percentile(np.abs(field), 95)),
            "min_swept_field_mm": float(np.min(swept)),
            "sample_count": int(len(points))}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--bad-faces", type=int, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    document = load_document(COMMON / "cases.json")
    case = next(item for item in document["cases"] if item["id"] == "tilted_crossing_paths")
    replay = replay_case(case, document["replay_policy"])
    radius = float(case["tool"]["radius_mm"])
    coordinates = np.concatenate([np.stack((item["start"], item["end"]))
                                  for item in replay["primitives"]])
    side_gap = 2.0 - float(np.max(np.abs(coordinates[:, :2]))) - radius
    if side_gap <= 0:
        raise ValueError("扫掠体可能触及箱体侧边")
    before = trimesh.load(args.before, force="mesh", process=False)
    after = trimesh.load(args.after, force="mesh", process=False)
    centers = np.asarray(before.triangles)[args.bad_faces].mean(axis=1)
    rows = {}
    for name, mesh in (("before", before), ("after", after)):
        points, count = local_points(mesh, centers)
        rows[name] = {"selected_faces": count, **field_residual(points, case, replay)}
    args.output.write_text(json.dumps({
        "case_id": args.case, "analytic_side_gap_mm": side_gap,
        "true_y_minus_2_edge": "z=0.15*x+0.2",
        "true_x_plus_2_edge": "z=0.3-0.1*y",
        "interpretation": "固定坏面中心0.12 mm邻域、每面15个重心样本的场残差；不是连续距离证书",
        "local": rows,
    }, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
