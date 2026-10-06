"""将残余锐边分叉点约束到输入网格的邻近锐边段。"""

import argparse
import json
from pathlib import Path

import numpy as np
import trimesh

from short_edge_collapse_probe import quality, topology_maps


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--diagnostics", required=True, type=Path)
    args = parser.parse_args()
    source = trimesh.load(args.source, force="mesh", process=False)
    mesh = trimesh.load(args.input, force="mesh", process=False)
    vertices = np.asarray(mesh.vertices, dtype=np.float64).copy()
    faces = np.asarray(mesh.faces, dtype=np.int64)
    source_edges = source.face_adjacency_edges[
        source.face_adjacency_angles > np.deg2rad(60)
    ]
    segments = np.asarray(source.vertices)[source_edges]
    starts = segments[:, 0]
    vectors = segments[:, 1] - starts
    lengths2 = np.sum(vectors**2, axis=1)
    feature_edges = mesh.face_adjacency_edges[
        mesh.face_adjacency_angles > np.deg2rad(30)
    ]
    degree = np.bincount(feature_edges.ravel(), minlength=len(vertices))
    incident, _ = topology_maps(faces)
    initial_bad = int(quality(vertices, faces)[0].sum())
    accepted = []
    # 只移动残余坏面上的分叉点，且投影位置必须来自源网格锐边段。
    for _ in range(20):
        bad, _, _ = quality(vertices, faces)
        branches = sorted(set(int(vertex) for vertex in faces[bad].ravel()
                              if degree[vertex] >= 3))
        choice = None
        for vertex in branches:
            point = vertices[vertex].copy()
            parameters = np.clip(np.sum((point - starts) * vectors, axis=1) / lengths2,
                                 0, 1)
            projections = starts + parameters[:, None] * vectors
            distances = np.linalg.norm(projections - point, axis=1)
            star = faces[sorted(incident[vertex])]
            old_bad, old_normals, old_angles = quality(vertices, star)
            old_count = int(old_bad.sum())
            for edge_id in np.argsort(distances)[:8]:
                if distances[edge_id] > 0.02:
                    break
                for fraction in (0.5, 1.0):
                    vertices[vertex] = point + fraction * (projections[edge_id] - point)
                    new_bad, new_normals, new_angles = quality(vertices, star)
                    if int(new_bad.sum()) >= old_count or np.any(new_bad & ~old_bad) \
                            or new_angles.min() < old_angles.min() - 1e-6 \
                            or np.any(np.einsum("ij,ij->i", new_normals, old_normals) <= 0.5):
                        continue
                    rank = (old_count - int(new_bad.sum()),
                            float(new_angles.min() - old_angles.min()), -float(distances[edge_id]))
                    if choice is None or rank > choice[0]:
                        choice = (rank, vertex, vertices[vertex].copy(), int(edge_id),
                                  float(fraction), float(distances[edge_id]))
            vertices[vertex] = point
        if choice is None:
            break
        _, vertex, position, edge_id, fraction, distance = choice
        vertices[vertex] = position
        accepted.append({"vertex": vertex, "source_edge": source_edges[edge_id].tolist(),
                         "fraction": fraction, "original_distance_mm": distance})
    output = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    args.output.write_text(trimesh.exchange.obj.export_obj(output, digits=17), encoding="utf-8")
    serialized = trimesh.load(args.output, force="mesh", process=False)
    args.diagnostics.write_text(json.dumps({
        "source": str(args.source), "input": str(args.input),
        "output": str(args.output), "initial_bad_faces": initial_bad,
        "serialized_bad_faces": int(quality(np.asarray(serialized.vertices),
                                            np.asarray(serialized.faces))[0].sum()),
        "accepted": accepted,
        "rule": "60度源锐边最近段0.02 mm内、分叉点半程或全程投影、邻域坏面减少且最小角不下降",
    }, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
