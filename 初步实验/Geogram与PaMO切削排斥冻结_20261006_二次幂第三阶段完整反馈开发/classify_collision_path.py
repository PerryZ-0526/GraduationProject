"""以独立点包含方法定位碰撞边连通路径的表面跨越位置。"""

import argparse
import json
from pathlib import Path

import numpy as np
import trimesh

from input_winding_audit import winding_numbers


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--path", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    mesh = trimesh.load(args.input, force="mesh", process=False)
    path = json.loads(args.path.read_text(encoding="utf-8"))
    points = np.asarray(path["path_points_mm"], dtype=np.float64)
    ray_inside = mesh.contains(points)
    winding = winding_numbers(mesh, points)
    winding_inside = np.abs(winding) > 0.5
    changes = np.flatnonzero(winding_inside[:-1] != winding_inside[1:])
    crossings = []
    for index in changes:
        direction = points[index + 1] - points[index]
        locations, _, triangle_indices = mesh.ray.intersects_location(
            ray_origins=[points[index]], ray_directions=[direction],
            multiple_hits=True,
        )
        distances = np.linalg.norm(locations - points[index], axis=1)
        within_edge = np.flatnonzero(distances <= np.linalg.norm(direction) + 1e-9)
        hits = []
        for hit in within_edge:
            face_id = int(triangle_indices[hit])
            triangle = mesh.vertices[mesh.faces[face_id]]
            basis = np.stack((triangle[1] - triangle[0],
                              triangle[2] - triangle[0]), axis=1)
            uv = np.linalg.lstsq(basis, locations[hit] - triangle[0], rcond=None)[0]
            hits.append({
                "point_mm": locations[hit].tolist(),
                "face_id": face_id,
                "face_area_mm2": float(mesh.area_faces[face_id]),
                "barycentric": [float(1 - uv.sum()), float(uv[0]), float(uv[1])],
            })
        crossings.append({
            "edge_index": int(index),
            "from_mm": points[index].tolist(),
            "to_mm": points[index + 1].tolist(),
            "from_winding": float(winding[index]),
            "to_winding": float(winding[index + 1]),
            "from_ray_inside": bool(ray_inside[index]),
            "to_ray_inside": bool(ray_inside[index + 1]),
            "source_triangle_hits": hits,
        })
    result = {
        "input": args.input.name,
        "path_grid_edges": path["path_grid_edges"],
        "start_winding": float(winding[0]),
        "end_winding": float(winding[-1]),
        "winding_ray_disagreements": int(np.count_nonzero(winding_inside != ray_inside)),
        "crossings": crossings,
        "interpretation": "离散点上找出未阻断碰撞边跨越实体表面的位置，不证明全局唯一漏点",
    }
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
