"""仅在质量失败邻域尝试受约束短边折叠。"""

import argparse
import json
from pathlib import Path

import numpy as np
import trimesh


def quality(vertices, faces):
    triangles = vertices[faces]
    sides = np.roll(triangles, -1, axis=1) - triangles
    lengths = np.linalg.norm(sides, axis=2)
    doubled_area = np.linalg.norm(np.cross(sides[:, 0], -sides[:, 2]), axis=1)
    q = np.divide(2 * np.sqrt(3) * doubled_area, np.sum(lengths**2, axis=1),
                  out=np.zeros(len(faces)), where=np.sum(lengths**2, axis=1) > 0)
    angles = []
    for corner in range(3):
        a = triangles[:, (corner + 1) % 3] - triangles[:, corner]
        b = triangles[:, (corner + 2) % 3] - triangles[:, corner]
        denominator = np.linalg.norm(a, axis=1) * np.linalg.norm(b, axis=1)
        cosine = np.divide(np.sum(a * b, axis=1), denominator,
                           out=np.ones(len(faces)), where=denominator > 0)
        angles.append(np.degrees(np.arccos(np.clip(cosine, -1, 1))))
    minimum_angle = np.min(np.stack(angles, axis=1), axis=1)
    bad = (minimum_angle < 25) | (q < 0.4) | (doubled_area <= 2e-12)
    cross = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    normals = np.divide(cross, doubled_area[:, None],
                        out=np.zeros_like(cross), where=doubled_area[:, None] > 0)
    return bad, normals, minimum_angle


def topology_maps(faces):
    incident = {}
    neighbors = {}
    for face_id, face in enumerate(faces):
        for vertex in face:
            incident.setdefault(int(vertex), set()).add(face_id)
        for first, second in ((face[0], face[1]), (face[1], face[2]),
                              (face[2], face[0])):
            a, b = int(first), int(second)
            neighbors.setdefault(a, set()).add(b)
            neighbors.setdefault(b, set()).add(a)
    return incident, neighbors


def try_collapse(vertices, faces, first, second, incident, neighbors):
    common = incident[first] & incident[second]
    if len(common) != 2:
        return None
    opposite = {int(vertex) for index in common for vertex in faces[index]
                if vertex not in (first, second)}
    if len(opposite) != 2 or neighbors[first] & neighbors[second] != opposite:
        return None
    affected = sorted(incident[first] | incident[second])
    retained = [index for index in affected if index not in common]
    old_faces = faces[affected]
    old_bad, old_normals, _ = quality(vertices, old_faces)
    edge_faces = faces[sorted(common)]
    _, edge_normals, _ = quality(vertices, edge_faces)
    if np.dot(edge_normals[0], edge_normals[1]) < np.cos(np.deg2rad(30)):
        return None
    replacement = faces[retained].copy()
    replacement[replacement == second] = first
    if len(replacement) and np.any(np.any(np.diff(np.sort(replacement, axis=1), axis=1) == 0, axis=1)):
        return None
    midpoint = (vertices[first] + vertices[second]) / 2
    proposed_vertices = vertices.copy()
    proposed_vertices[first] = midpoint
    new_bad, new_normals, _ = quality(proposed_vertices, replacement)
    old_retained_normals = old_normals[np.isin(affected, retained)]
    if np.any(np.einsum("ij,ij->i", new_normals, old_retained_normals) <= 0.5):
        return None
    if int(new_bad.sum()) >= int(old_bad.sum()):
        return None
    return midpoint, int(old_bad.sum() - new_bad.sum()), sorted(common)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--diagnostics", required=True, type=Path)
    args = parser.parse_args()
    mesh = trimesh.load(args.input, force="mesh", process=False)
    vertices = np.asarray(mesh.vertices, dtype=np.float64).copy()
    faces = np.asarray(mesh.faces, dtype=np.int64).copy()
    initial_bad = int(quality(vertices, faces)[0].sum())
    accepted = []
    for _ in range(100):
        bad, _, _ = quality(vertices, faces)
        incident, neighbors = topology_maps(faces)
        candidates = set()
        for face in faces[bad]:
            for a, b in ((face[0], face[1]), (face[1], face[2]), (face[2], face[0])):
                a, b = sorted((int(a), int(b)))
                length = np.linalg.norm(vertices[a] - vertices[b])
                if length <= 0.02:
                    candidates.add((length, a, b))
        change = None
        for length, first, second in sorted(candidates):
            if length / 2 > 0.012:
                continue
            proposed = try_collapse(vertices, faces, first, second, incident, neighbors)
            if proposed is not None:
                change = (first, second, length, *proposed)
                break
        if change is None:
            break
        first, second, length, midpoint, improvement, removed = change
        vertices[first] = midpoint
        faces[faces == second] = first
        faces = np.delete(faces, removed, axis=0)
        accepted.append({"edge": [first, second], "length_mm": float(length),
                         "local_bad_reduction": improvement})
    output = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    output.remove_unreferenced_vertices()
    output.export(args.output)
    args.diagnostics.write_text(json.dumps({
        "input": str(args.input), "output": str(args.output),
        "initial_bad_faces": initial_bad,
        "final_bad_faces": int(quality(np.asarray(output.vertices), np.asarray(output.faces))[0].sum()),
        "accepted": accepted,
        "rule": "短边不超过0.02 mm，边两侧夹角不超过30度，折叠位移不超过0.012 mm，局部坏面数严格下降",
    }, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
