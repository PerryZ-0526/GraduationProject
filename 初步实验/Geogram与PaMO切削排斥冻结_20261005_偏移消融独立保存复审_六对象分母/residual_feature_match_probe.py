"""测量残余坏面分叉点到输入网格锐边的距离。"""

import argparse
import json
from pathlib import Path

import numpy as np
import trimesh

from short_edge_collapse_probe import quality


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    source = trimesh.load(args.source, force="mesh", process=False)
    candidate = trimesh.load(args.candidate, force="mesh", process=False)
    source_mask = source.face_adjacency_angles > np.deg2rad(30)
    source_edges = source.face_adjacency_edges[source_mask]
    source_angles = np.rad2deg(source.face_adjacency_angles[source_mask])
    candidate_edges = candidate.face_adjacency_edges[
        candidate.face_adjacency_angles > np.deg2rad(30)
    ]
    degree = np.bincount(candidate_edges.ravel(), minlength=len(candidate.vertices))
    bad, _, angles = quality(np.asarray(candidate.vertices), np.asarray(candidate.faces))
    segments = np.asarray(source.vertices)[source_edges]
    starts = segments[:, 0]
    vectors = segments[:, 1] - starts
    lengths2 = np.sum(vectors**2, axis=1)
    rows = []
    for face_id in np.flatnonzero(bad):
        vertices = candidate.faces[face_id]
        branches = []
        for vertex_id in vertices[degree[vertices] >= 3]:
            point = candidate.vertices[vertex_id]
            parameters = np.clip(np.sum((point - starts) * vectors, axis=1) / lengths2,
                                 0, 1)
            nearest = starts + parameters[:, None] * vectors
            distances = np.linalg.norm(nearest - point, axis=1)
            edge_id = int(np.argmin(distances))
            branches.append({
                "vertex_id": int(vertex_id),
                "distance_to_source_feature_mm": float(distances[edge_id]),
                "source_feature_edge": source_edges[edge_id].tolist(),
                "source_feature_dihedral_deg": float(source_angles[edge_id]),
            })
        rows.append({
            "face_id": int(face_id),
            "min_angle_deg": float(angles[face_id]),
            "center_mm": candidate.vertices[vertices].mean(axis=0).tolist(),
            "candidate_feature_degrees": degree[vertices].tolist(),
            "branch_vertices": branches,
        })
    result = {
        "source": str(args.source),
        "candidate": str(args.candidate),
        "source_feature_edges_30deg": len(source_edges),
        "candidate_feature_edges_30deg": len(candidate_edges),
        "bad_faces": len(rows),
        "bad_faces_touching_branch": sum(bool(row["branch_vertices"]) for row in rows),
        "rows": rows,
        "interpretation": "30度锐边近邻仅为网格分类，不能单独证明解析CSG交线对应",
    }
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")


if __name__ == "__main__":
    main()
