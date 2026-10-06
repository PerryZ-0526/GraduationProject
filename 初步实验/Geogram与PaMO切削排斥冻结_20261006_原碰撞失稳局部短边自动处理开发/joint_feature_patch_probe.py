"""固定锐边分叉点，联合调整坏面周围可移动顶点。"""

import argparse
import json
from pathlib import Path

import numpy as np
from scipy.optimize import differential_evolution
import trimesh

from feature_tangent_relax_probe import feature_tangents
from short_edge_collapse_probe import quality, topology_maps


def variable_bases(mesh):
    tangents = feature_tangents(mesh)
    edges = mesh.face_adjacency_edges[mesh.face_adjacency_angles > np.deg2rad(30)]
    degree = np.bincount(edges.ravel(), minlength=len(mesh.vertices))
    bases = {vertex: (direction[:, None], 0.03)
             for vertex, direction in tangents.items()}
    for vertex in np.flatnonzero(degree == 0):
        normal = np.asarray(mesh.vertex_normals[vertex], dtype=np.float64)
        axis = np.array([1.0, 0.0, 0.0])
        if abs(np.dot(axis, normal)) > 0.9:
            axis = np.array([0.0, 1.0, 0.0])
        first = np.cross(normal, axis)
        norm = np.linalg.norm(first)
        if norm <= 1e-12:
            continue
        first /= norm
        second = np.cross(normal, first)
        bases[int(vertex)] = (np.stack((first, second), axis=1), 0.02)
    return bases


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--diagnostics", required=True, type=Path)
    parser.add_argument("--target-angle-deg", type=float, choices=(25.0, 25.2), default=25.2)
    parser.add_argument("--accept-angle-deg", type=float, choices=(25.0, 25.1), default=25.1)
    parser.add_argument("--obj-digits", type=int, choices=(8, 17), default=17)
    args = parser.parse_args()
    mesh = trimesh.load(args.input, force="mesh", process=False)
    vertices = np.asarray(mesh.vertices, dtype=np.float64).copy()
    initial = vertices.copy()
    faces = np.asarray(mesh.faces, dtype=np.int64)
    bases = variable_bases(mesh)
    incident, _ = topology_maps(faces)
    initial_bad = int(quality(vertices, faces)[0].sum())
    accepted = []
    # 局部目标先减少角度缺口，发布条件再检查全邻域坏面数及最差角。
    for _ in range(20):
        bad, _, angles = quality(vertices, faces)
        choice = None
        for face_id in np.flatnonzero(bad):
            movable = [int(vertex) for vertex in faces[face_id] if int(vertex) in bases]
            if not movable:
                continue
            star_ids = sorted(set().union(*(incident[vertex] for vertex in movable)))
            star = faces[star_ids]
            old_bad, old_normals, old_angles = quality(vertices, star)
            old_count = int(old_bad.sum())
            original = vertices[movable].copy()
            slices = {}
            bounds = []
            for vertex in movable:
                basis, limit = bases[vertex]
                start = len(bounds)
                bounds.extend([(-limit, limit)] * basis.shape[1])
                slices[vertex] = slice(start, len(bounds))

            def set_positions(parameters):
                proposed = []
                for index, vertex in enumerate(movable):
                    basis, limit = bases[vertex]
                    delta = basis @ parameters[slices[vertex]]
                    position = original[index] + delta
                    if np.linalg.norm(initial[vertex] - position) > limit + 1e-9:
                        vertices[movable] = original
                        return False
                    proposed.append(position)
                vertices[movable] = proposed
                return True

            def objective(parameters):
                if not set_positions(parameters):
                    return 1e9
                _, normals, trial_angles = quality(vertices, star)
                if np.any(np.einsum("ij,ij->i", normals, old_normals) <= 0.5):
                    return 1e9
                return float(np.square(np.maximum(args.target_angle_deg - trial_angles, 0)).sum()
                             + 0.01 * np.square(parameters).sum())

            result = differential_evolution(
                objective, bounds, seed=20260927 + int(face_id),
                maxiter=80, popsize=8, polish=True, tol=1e-4,
            )
            feasible = set_positions(result.x)
            new_bad, new_normals, new_angles = quality(vertices, star)
            if feasible and int(new_bad.sum()) < old_count and not np.any(new_bad & ~old_bad) \
                    and np.all(new_angles[old_bad & ~new_bad] >= args.accept_angle_deg) \
                    and new_angles.min() >= old_angles.min() - 1e-6 \
                    and np.all(np.einsum("ij,ij->i", new_normals, old_normals) > 0.5):
                rank = (old_count - int(new_bad.sum()),
                        float(new_angles.min() - old_angles.min()))
                positions = vertices[movable].copy()
                if choice is None or rank > choice[0]:
                    choice = (rank, int(face_id), movable, positions)
            vertices[movable] = original
        if choice is None:
            break
        _, face_id, movable, positions = choice
        vertices[movable] = positions
        accepted.append({"face_id": face_id, "vertices": movable})
    output = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    # 两档导出精度用于复核阈值边界；发布候选使用17位坐标。
    args.output.write_text(trimesh.exchange.obj.export_obj(output, digits=args.obj_digits), encoding="utf-8")
    serialized = trimesh.load(args.output, force="mesh", process=False)
    args.diagnostics.write_text(json.dumps({
        "input": str(args.input), "output": str(args.output),
        "initial_bad_faces": initial_bad,
        "final_bad_faces": int(quality(vertices, faces)[0].sum()),
        "serialized_bad_faces": int(quality(np.asarray(serialized.vertices),
                                            np.asarray(serialized.faces))[0].sum()),
        "target_angle_deg": args.target_angle_deg,
        "accept_angle_deg": args.accept_angle_deg,
        "obj_digits": args.obj_digits,
        "accepted": accepted,
        "rule": "分叉点固定，二度锐边切向或非锐边切平面联合调整；局部坏面数下降、无新增坏面、局部最小角不下降",
    }, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
