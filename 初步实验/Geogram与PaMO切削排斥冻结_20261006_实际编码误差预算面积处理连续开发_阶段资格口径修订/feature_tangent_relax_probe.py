"""沿近直线锐边切向移动顶点，探查剩余坏面的局部可修复性。"""

import argparse
import json
from pathlib import Path

import numpy as np
import trimesh

from short_edge_collapse_probe import quality, topology_maps


def feature_tangents(mesh):
    feature_edges = mesh.face_adjacency_edges[
        mesh.face_adjacency_angles > np.deg2rad(30)
    ]
    neighbors = {}
    for first, second in feature_edges:
        neighbors.setdefault(int(first), set()).add(int(second))
        neighbors.setdefault(int(second), set()).add(int(first))
    tangents = {}
    vertices = np.asarray(mesh.vertices, dtype=np.float64)
    for vertex, linked in neighbors.items():
        if len(linked) != 2:
            continue
        first, second = sorted(linked)
        a = vertices[first] - vertices[vertex]
        b = vertices[second] - vertices[vertex]
        a /= np.linalg.norm(a)
        b /= np.linalg.norm(b)
        # 只沿近直线的特征线移动；尖角和分叉保持固定。
        if np.dot(a, b) > -np.cos(np.deg2rad(30)):
            continue
        tangent = vertices[second] - vertices[first]
        tangent /= np.linalg.norm(tangent)
        tangents[vertex] = tangent
    return tangents


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--diagnostics", required=True, type=Path)
    parser.add_argument("--max-step-mm", type=float, choices=(0.015, 0.03), default=0.015)
    args = parser.parse_args()
    mesh = trimesh.load(args.input, force="mesh", process=False)
    vertices = np.asarray(mesh.vertices, dtype=np.float64).copy()
    starting_vertices = vertices.copy()
    faces = np.asarray(mesh.faces, dtype=np.int64)
    tangents = feature_tangents(mesh)
    incident, _ = topology_maps(faces)
    initial_bad = int(quality(vertices, faces)[0].sum())
    accepted = []
    # 对单点星形邻域逐次审计，禁止把坏面转移到邻面。
    for _ in range(100):
        global_bad, _, _ = quality(vertices, faces)
        candidates = sorted(set(int(vertex) for vertex in faces[global_bad].ravel())
                            & set(tangents))
        choice = None
        for vertex in candidates:
            star = faces[sorted(incident[vertex])]
            old_bad, old_normals, old_angles = quality(vertices, star)
            old_count = int(old_bad.sum())
            old_penalty = float(np.square(np.maximum(25 - old_angles, 0)).sum())
            original = vertices[vertex].copy()
            steps = np.arange(0.005, args.max_step_mm + 1e-9, 0.005)
            for step in np.concatenate((-steps[::-1], steps)):
                vertices[vertex] = original + step * tangents[vertex]
                if np.linalg.norm(vertices[vertex] - starting_vertices[vertex]) > args.max_step_mm + 1e-9:
                    continue
                new_bad, new_normals, new_angles = quality(vertices, star)
                new_count = int(new_bad.sum())
                if new_count >= old_count or np.any(
                    np.einsum("ij,ij->i", new_normals, old_normals) <= 0.5
                ):
                    continue
                new_penalty = float(np.square(np.maximum(25 - new_angles, 0)).sum())
                rank = (old_count - new_count, old_penalty - new_penalty, -abs(step))
                if choice is None or rank > choice[0]:
                    choice = (rank, vertex, original + step * tangents[vertex], step)
            vertices[vertex] = original
        if choice is None:
            break
        _, vertex, position, step = choice
        vertices[vertex] = position
        accepted.append({"vertex": vertex, "step_mm": float(step)})
    output = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    output.export(args.output)
    args.diagnostics.write_text(json.dumps({
        "input": str(args.input), "output": str(args.output),
        "initial_bad_faces": initial_bad,
        "final_bad_faces": int(quality(vertices, faces)[0].sum()),
        "eligible_feature_vertices": len(tangents),
        "max_step_mm": args.max_step_mm,
        "accepted": accepted,
        "rule": "锐边二度顶点、两段夹角至少150度、沿切向移动受最大累计位移约束、邻域坏面数严格下降且不翻面",
    }, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
