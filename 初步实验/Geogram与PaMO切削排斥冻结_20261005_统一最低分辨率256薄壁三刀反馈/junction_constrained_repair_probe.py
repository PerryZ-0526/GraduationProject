"""约束锐边分叉到邻近输入锐边段，联合调整局部顶点。"""

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
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--diagnostics", required=True, type=Path)
    args = parser.parse_args()
    source = trimesh.load(args.source, force="mesh", process=False)
    mesh = trimesh.load(args.input, force="mesh", process=False)
    vertices = np.asarray(mesh.vertices, dtype=np.float64).copy()
    starting_vertices = vertices.copy()
    faces = np.asarray(mesh.faces, dtype=np.int64)
    edge_segments = np.asarray(source.vertices)[source.face_adjacency_edges[
        source.face_adjacency_angles > np.deg2rad(60)
    ]]
    starts = edge_segments[:, 0]
    vectors = edge_segments[:, 1] - starts
    lengths2 = np.sum(vectors**2, axis=1)
    detected = mesh.face_adjacency_edges[
        mesh.face_adjacency_angles > np.deg2rad(30)
    ]
    degree = np.bincount(detected.ravel(), minlength=len(vertices))
    tangents = feature_tangents(mesh)
    incident, _ = topology_maps(faces)
    initial_bad = int(quality(vertices, faces)[0].sum())
    accepted = []
    # 分叉点只在来源锐边段附近联合移动，且必须直接消去坏面。
    for _ in range(20):
        bad, _, _ = quality(vertices, faces)
        choice = None
        for face_id in np.flatnonzero(bad):
            face = faces[face_id]
            branches = [int(vertex) for vertex in face if degree[vertex] >= 3]
            if len(branches) != 1:
                continue
            branch = branches[0]
            others = [int(vertex) for vertex in face if vertex != branch]
            if any(vertex not in tangents for vertex in others):
                continue
            point = vertices[branch].copy()
            parameters = np.clip(np.sum((point - starts) * vectors, axis=1) / lengths2,
                                 0, 1)
            projected = starts + parameters[:, None] * vectors
            distances = np.linalg.norm(projected - point, axis=1)
            edge_id = int(np.argmin(distances))
            if distances[edge_id] > 0.02:
                continue
            projection = projected[edge_id]
            source_tangent = vectors[edge_id] / np.sqrt(lengths2[edge_id])
            star_ids = sorted(set().union(*(incident[int(vertex)] for vertex in face)))
            star = faces[star_ids]
            original = vertices[face].copy()
            old_bad, old_normals, old_angles = quality(vertices, star)
            old_count = int(old_bad.sum())
            positions = {int(vertex): original[index] for index, vertex in enumerate(face)}

            def move(trial):
                proposals = {
                    others[index]: positions[others[index]] + trial[index] * tangents[others[index]]
                    for index in range(2)
                }
                proposals[branch] = projection + trial[2] * source_tangent \
                    + trial[3] * (point - projection)
                if any(np.linalg.norm(position - starting_vertices[vertex]) > 0.03
                       for vertex, position in proposals.items()):
                    vertices[face] = original
                    return False
                for vertex, position in proposals.items():
                    vertices[vertex] = position
                return True

            def objective(trial):
                if not move(trial):
                    return 1e9
                trial_bad, trial_normals, trial_angles = quality(vertices, star)
                if np.any(np.einsum("ij,ij->i", trial_normals, old_normals) <= 0.5):
                    return 1e9
                return float(np.square(np.maximum(25.2 - trial_angles, 0)).sum()
                             + 1000 * np.count_nonzero(trial_bad & ~old_bad))

            result = differential_evolution(
                objective, [(-0.03, 0.03)] * 3 + [(0, 1)],
                seed=20260927 + int(face_id), maxiter=150, popsize=12, polish=True,
            )
            feasible = move(result.x)
            new_bad, new_normals, new_angles = quality(vertices, star)
            repaired = old_bad & ~new_bad
            if feasible and int(new_bad.sum()) < old_count and not np.any(new_bad & ~old_bad) \
                    and np.all(new_angles[repaired] >= 25.1) \
                    and new_angles.min() >= old_angles.min() - 1e-6 \
                    and np.all(np.einsum("ij,ij->i", new_normals, old_normals) > 0.5):
                rank = (old_count - int(new_bad.sum()),
                        float(new_angles.min() - old_angles.min()))
                if choice is None or rank > choice[0]:
                    choice = (rank, int(face_id), face.copy(), vertices[face].copy(),
                              int(edge_id), float(distances[edge_id]))
            vertices[face] = original
        if choice is None:
            break
        _, face_id, face, positions, edge_id, distance = choice
        vertices[face] = positions
        accepted.append({"face_id": face_id, "vertices": face.tolist(),
                         "source_edge": edge_segments[edge_id].tolist(),
                         "original_source_distance_mm": distance})
    output = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    args.output.write_text(trimesh.exchange.obj.export_obj(output, digits=17), encoding="utf-8")
    serialized = trimesh.load(args.output, force="mesh", process=False)
    args.diagnostics.write_text(json.dumps({
        "source": str(args.source), "input": str(args.input), "output": str(args.output),
        "initial_bad_faces": initial_bad,
        "serialized_bad_faces": int(quality(np.asarray(serialized.vertices),
                                            np.asarray(serialized.faces))[0].sum()),
        "accepted": accepted,
        "rule": "单个三度以上分叉及两个近直线二度锐边点、60度来源边0.02 mm内、累计位移0.03 mm、修好面角度至少25.1度",
    }, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
