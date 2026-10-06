"""探查固定三角连接下，来源约束交会邻域能否跨过质量角门槛。"""

import argparse
import json
from pathlib import Path

import numpy as np
from scipy.optimize import differential_evolution
import trimesh

from feature_tangent_relax_probe import feature_tangents
from short_edge_collapse_probe import quality, topology_maps


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--face-id", required=True, type=int)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    source = trimesh.load(args.source, force="mesh", process=False)
    mesh = trimesh.load(args.input, force="mesh", process=False)
    vertices = np.asarray(mesh.vertices, dtype=np.float64).copy()
    faces = np.asarray(mesh.faces, dtype=np.int64)
    feature_edges = mesh.face_adjacency_edges[
        mesh.face_adjacency_angles > np.deg2rad(30)
    ]
    degree = np.bincount(feature_edges.ravel(), minlength=len(vertices))
    face = faces[args.face_id]
    branches = [int(vertex) for vertex in face if degree[vertex] >= 3]
    if len(branches) != 1:
        raise ValueError("固定面必须恰有一个锐边分叉顶点")
    branch = branches[0]
    others = [int(vertex) for vertex in face if vertex != branch]
    tangents = feature_tangents(mesh)
    if any(vertex not in tangents for vertex in others):
        raise ValueError("另外两个顶点必须有近直线锐边切向")
    source_edges = source.face_adjacency_edges[
        source.face_adjacency_angles > np.deg2rad(60)
    ]
    segments = np.asarray(source.vertices)[source_edges]
    starts = segments[:, 0]
    vectors = segments[:, 1] - starts
    point = vertices[branch].copy()
    parameters = np.clip(np.sum((point - starts) * vectors, axis=1)
                         / np.sum(vectors**2, axis=1), 0, 1)
    projections = starts + parameters[:, None] * vectors
    edge_id = int(np.argmin(np.linalg.norm(projections - point, axis=1)))
    projection = projections[edge_id]
    source_tangent = vectors[edge_id] / np.linalg.norm(vectors[edge_id])
    incident, _ = topology_maps(faces)
    star_ids = sorted(set().union(*(incident[int(vertex)] for vertex in face)))
    star = faces[star_ids]
    original = vertices[face].copy()
    old_bad, old_normals, old_angles = quality(vertices, star)

    def move(trial):
        for index, vertex in enumerate(others):
            vertices[vertex] = original[np.where(face == vertex)[0][0]] \
                + trial[index] * tangents[vertex]
        vertices[branch] = projection + trial[2] * source_tangent \
            + trial[3] * (point - projection)
        return all(np.linalg.norm(vertices[vertex]
                                  - original[np.where(face == vertex)[0][0]]) <= 0.03
                   for vertex in face)

    def objective(trial):
        if not move(trial):
            return 1e9
        bad, normals, angles = quality(vertices, star)
        if np.any(np.einsum("ij,ij->i", normals, old_normals) <= 0.5):
            return 1e9
        return float(np.square(np.maximum(25.2 - angles, 0)).sum()
                     + 1000 * np.count_nonzero(bad & ~old_bad))

    result = differential_evolution(
        objective, [(-0.03, 0.03)] * 3 + [(0, 1)],
        seed=20260927 + args.face_id, maxiter=150, popsize=12, polish=True,
    )
    feasible = move(result.x)
    new_bad, new_normals, new_angles = quality(vertices, star)
    face_index = star_ids.index(args.face_id)
    output = {
        "source": str(args.source), "input": str(args.input),
        "face_id": args.face_id, "face_vertices": face.tolist(),
        "source_edge": source_edges[edge_id].tolist(),
        "source_distance_mm": float(np.linalg.norm(projection - point)),
        "old_star_bad_faces": int(old_bad.sum()),
        "new_star_bad_faces": int(new_bad.sum()),
        "old_star_min_angle_deg": float(old_angles.min()),
        "new_star_min_angle_deg": float(new_angles.min()),
        "old_target_angle_deg": float(old_angles[face_index]),
        "new_target_angle_deg": float(new_angles[face_index]),
        "position_feasible": bool(feasible),
        "new_bad_from_old_good": int(np.count_nonzero(new_bad & ~old_bad)),
        "normal_flip_faces": int(np.count_nonzero(
            np.einsum("ij,ij->i", new_normals, old_normals) <= 0.5)),
        "parameters": result.x.tolist(),
        "interpretation": "固定连接的单次有限数值搜索；无全局不可行性证明",
    }
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")


if __name__ == "__main__":
    main()
