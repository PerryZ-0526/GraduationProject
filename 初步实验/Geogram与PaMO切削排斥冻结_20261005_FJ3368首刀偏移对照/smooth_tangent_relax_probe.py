"""仅移动非锐边顶点，探查边缘残余坏面的可修复性。"""

import argparse
import json
from pathlib import Path

import numpy as np
import trimesh

from short_edge_collapse_probe import quality, topology_maps


def tangent_directions(normal):
    axis = np.array([1.0, 0.0, 0.0])
    if abs(np.dot(axis, normal)) > 0.9:
        axis = np.array([0.0, 1.0, 0.0])
    first = np.cross(normal, axis)
    first /= np.linalg.norm(first)
    second = np.cross(normal, first)
    directions = [first, second, first + second, first - second]
    return [direction / np.linalg.norm(direction) * sign
            for direction in directions for sign in (-1, 1)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--diagnostics", required=True, type=Path)
    args = parser.parse_args()
    mesh = trimesh.load(args.input, force="mesh", process=False)
    vertices = np.asarray(mesh.vertices, dtype=np.float64).copy()
    initial = vertices.copy()
    faces = np.asarray(mesh.faces, dtype=np.int64)
    feature_edges = mesh.face_adjacency_edges[
        mesh.face_adjacency_angles > np.deg2rad(30)
    ]
    protected = set(int(vertex) for vertex in feature_edges.ravel())
    incident, _ = topology_maps(faces)
    initial_bad = int(quality(vertices, faces)[0].sum())
    accepted = []
    # 每次只接受星形邻域坏面数下降且所有受影响面不翻转的位移。
    for _ in range(100):
        bad, _, _ = quality(vertices, faces)
        candidates = sorted(set(int(vertex) for vertex in faces[bad].ravel()) - protected)
        choice = None
        for vertex in candidates:
            star = faces[sorted(incident[vertex])]
            old_bad, old_normals, old_angles = quality(vertices, star)
            normal = np.sum(old_normals, axis=0)
            norm = np.linalg.norm(normal)
            if norm <= 1e-12:
                continue
            normal /= norm
            original = vertices[vertex].copy()
            old_count = int(old_bad.sum())
            old_penalty = float(np.square(np.maximum(25 - old_angles, 0)).sum())
            for length in (0.005, 0.01, 0.02):
                for direction in tangent_directions(normal):
                    vertices[vertex] = original + length * direction
                    if np.linalg.norm(vertices[vertex] - initial[vertex]) > 0.02 + 1e-9:
                        continue
                    new_bad, new_normals, new_angles = quality(vertices, star)
                    new_count = int(new_bad.sum())
                    if new_count >= old_count or np.any(
                        np.einsum("ij,ij->i", new_normals, old_normals) <= 0.5
                    ):
                        continue
                    new_penalty = float(np.square(np.maximum(25 - new_angles, 0)).sum())
                    rank = (old_count - new_count, old_penalty - new_penalty, -length)
                    if choice is None or rank > choice[0]:
                        choice = (rank, vertex, vertices[vertex].copy(), length)
            vertices[vertex] = original
        if choice is None:
            break
        _, vertex, position, length = choice
        vertices[vertex] = position
        accepted.append({"vertex": vertex, "move_mm": length})
    output = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    output.export(args.output)
    args.diagnostics.write_text(json.dumps({
        "input": str(args.input), "output": str(args.output),
        "initial_bad_faces": initial_bad,
        "final_bad_faces": int(quality(vertices, faces)[0].sum()),
        "accepted": accepted,
        "rule": "非锐边顶点、切平面八方向、累计位移不超过0.02 mm、局部坏面数严格下降且不翻面",
    }, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
