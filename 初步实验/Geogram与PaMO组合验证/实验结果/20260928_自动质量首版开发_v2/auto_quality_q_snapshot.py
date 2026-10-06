"""从完整PaMO网格自动选择有限局部翻边与折叠；失败时拒绝交付。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from time import perf_counter

import numpy as np
import pymeshlab as pm
import trimesh
from scipy.spatial import cKDTree

from quality_flip_probe import edges, face_values
from short_edge_collapse_probe import quality, topology_maps


MAX_ACCEPTED = 80
MAX_EDGE_MM = 0.05
MAX_MOVE_MM = 0.03
MAX_SOURCE_DRIFT_MM = 0.08
FEATURE_DISTANCE_MM = 0.03


def source_features(mesh: trimesh.Trimesh) -> tuple[np.ndarray, np.ndarray, cKDTree | None]:
    """从Geogram面邻接提取锐边；不把它直接解释为真实CSG交线。"""
    pairs = mesh.face_adjacency
    dots = np.einsum("ij,ij->i", mesh.face_normals[pairs[:, 0]], mesh.face_normals[pairs[:, 1]])
    selected = mesh.face_adjacency_edges[dots < np.cos(np.deg2rad(60))]
    segments = np.asarray(mesh.vertices[selected], dtype=np.float64)
    centers = segments.mean(axis=1) if len(segments) else np.empty((0, 3))
    return segments, centers, cKDTree(centers) if len(centers) else None


def edge_feature_state(a: np.ndarray, b: np.ndarray, features: tuple) -> str:
    """返回保护、非特征或多义；多义边不操作。"""
    segments, centers, tree = features
    if tree is None:
        return "smooth"
    midpoint = (a + b) / 2
    # 检索半径覆盖来源锐边的半长，避免长边的端点附近被误判为无特征。
    half_length = np.max(np.linalg.norm(segments[:, 1] - segments[:, 0], axis=1)) / 2
    indices = tree.query_ball_point(midpoint, FEATURE_DISTANCE_MM + half_length)
    matches = []
    direction = b - a
    direction /= max(np.linalg.norm(direction), 1e-15)
    for index in indices:
        first, second = segments[index]
        tangent = second - first
        length2 = float(tangent @ tangent)
        if length2 <= 0:
            continue
        t = np.clip(((midpoint - first) @ tangent) / length2, 0, 1)
        distance = np.linalg.norm(midpoint - (first + t * tangent))
        if distance <= FEATURE_DISTANCE_MM:
            matches.append(abs(direction @ tangent / np.sqrt(length2)))
    if not matches:
        return "smooth"
    return "protected" if max(matches) >= 0.8 and min(matches) >= 0.5 else "ambiguous"


def collision_count(vertices: np.ndarray, faces: np.ndarray) -> int:
    mesh_set = pm.MeshSet()
    mesh_set.add_mesh(pm.Mesh(vertices, faces))
    mesh_set.compute_selection_by_self_intersections_per_face()
    return int(mesh_set.current_mesh().selected_face_number())


def source_distance(source: trimesh.Trimesh, points: np.ndarray) -> float:
    _, distances, _ = trimesh.proximity.closest_point(source, points)
    return float(np.max(distances, initial=0))


def flip_candidate(vertices: np.ndarray, faces: np.ndarray, edge: tuple[int, int], owners: list[int]):
    if len(owners) != 2:
        return None
    first_id, second_id = owners
    first, second = faces[first_id], faces[second_id]
    a, b = edge
    if not any(first[i] == a and first[(i + 1) % 3] == b for i in range(3)):
        a, b = b, a
    c = next(int(v) for v in first if v not in edge)
    d = next(int(v) for v in second if v not in edge)
    if c == d:
        return None
    before = [face_values(vertices, triangle) for triangle in (first, second)]
    if min(value[0] for value in before) <= 1e-12:
        return None
    if before[0][3] @ before[1][3] < np.cos(np.deg2rad(30)):
        return None
    if max(abs((vertices[c] - vertices[a]) @ before[1][3]),
           abs((vertices[d] - vertices[a]) @ before[0][3])) > 0.005:
        return None
    replacement = np.array(((c, d, b), (d, c, a)), dtype=np.int64)
    after = [face_values(vertices, triangle) for triangle in replacement]
    old_bad = sum(area <= 1e-12 or q < 0.4 or angle < 25 for area, q, angle, _ in before)
    new_bad = sum(area <= 1e-12 or q < 0.4 or angle < 25 for area, q, angle, _ in after)
    if new_bad >= old_bad or any(area <= 1e-12 for area, _, _, _ in after):
        return None
    normal = before[0][3] + before[1][3]
    normal /= np.linalg.norm(normal)
    if any(value[3] @ normal <= 0.9 for value in after):
        return None
    proposed = faces.copy()
    proposed[[first_id, second_id]] = replacement
    return vertices, proposed, old_bad - new_bad


def collapse_candidates(source: trimesh.Trimesh, vertices: np.ndarray, faces: np.ndarray,
                        edge: tuple[int, int], incident: dict, neighbors: dict):
    first, second = edge
    common = incident[first] & incident[second]
    opposite = {int(v) for face_id in common for v in faces[face_id] if v not in edge}
    if len(common) != 2 or len(opposite) != 2 or neighbors[first] & neighbors[second] != opposite:
        return
    affected = sorted(incident[first] | incident[second])
    retained = [index for index in affected if index not in common]
    old_bad, old_normals, _ = quality(vertices, faces[affected])
    edge_normals = quality(vertices, faces[sorted(common)])[1]
    if edge_normals[0] @ edge_normals[1] < np.cos(np.deg2rad(30)):
        return
    midpoint = (vertices[first] + vertices[second]) / 2
    projected = trimesh.proximity.closest_point(source, midpoint[None, :])[0][0]
    locations = (vertices[first], vertices[second], midpoint, projected)
    for point in locations:
        if max(np.linalg.norm(vertices[first] - point), np.linalg.norm(vertices[second] - point)) > MAX_MOVE_MM:
            continue
        proposed_vertices = vertices.copy()
        proposed_vertices[first] = point
        proposed_faces = faces.copy()
        proposed_faces[proposed_faces == second] = first
        proposed_faces = np.delete(proposed_faces, sorted(common), axis=0)
        new_faces = faces[retained].copy()
        new_faces[new_faces == second] = first
        if np.any(np.diff(np.sort(new_faces, axis=1), axis=1) == 0):
            continue
        new_bad, new_normals, new_angles = quality(proposed_vertices, new_faces)
        mask = np.isin(affected, retained)
        if (int(new_bad.sum()) >= int(old_bad.sum()) or
                np.any(new_bad & ~old_bad[mask]) or
                np.any(new_angles[~new_bad] < 25.1) or
                np.any(np.einsum("ij,ij->i", new_normals, old_normals[mask]) <= 0.9)):
            continue
        yield proposed_vertices, proposed_faces, int(old_bad.sum() - new_bad.sum()), point


def optimize(source: trimesh.Trimesh, original: trimesh.Trimesh, with_source: bool = True) -> tuple:
    """有限次数的事务式候选评估；全局验收失败只返回拒绝。"""
    started = perf_counter()
    vertices = np.asarray(original.vertices, dtype=np.float64).copy()
    faces = np.asarray(original.faces, dtype=np.int64).copy()
    features = source_features(source)
    if collision_count(vertices, faces):
        return original, {"status": "rejected_input_self_intersection", "accepted": []}
    initial_bad = int(quality(vertices, faces)[0].sum())
    accepted = []
    for _ in range(min(initial_bad, MAX_ACCEPTED)):
        bad = quality(vertices, faces)[0]
        if not bad.any():
            break
        incident, neighbors = topology_maps(faces)
        edge_owners = {}
        for face_id, triangle in enumerate(faces):
            for edge in edges(triangle):
                edge_owners.setdefault(edge, []).append(face_id)
        candidates = {edge for triangle in faces[bad] for edge in edges(triangle)}
        ranked = sorted(candidates, key=lambda edge: (np.linalg.norm(vertices[edge[0]] - vertices[edge[1]]), edge))
        change = None
        for edge in ranked:
            if with_source and edge_feature_state(vertices[edge[0]], vertices[edge[1]], features) != "smooth":
                continue
            old_length = np.linalg.norm(vertices[edge[0]] - vertices[edge[1]])
            proposals = []
            flipped = flip_candidate(vertices, faces, edge, edge_owners[edge])
            if flipped is not None and tuple(sorted(set(faces[edge_owners[edge]].ravel()) - set(edge))) not in edge_owners:
                proposals.append(("flip", *flipped, None))
            if old_length <= MAX_EDGE_MM:
                proposals.extend(("collapse", *item) for item in collapse_candidates(
                    source, vertices, faces, edge, incident, neighbors))
            for name, new_vertices, new_faces, reduction, point in proposals:
                probe = (new_vertices[new_faces[edge_owners[edge][0]]].mean(axis=0)[None, :]
                         if name == "flip" else point[None, :])
                if source_distance(source, probe) > MAX_SOURCE_DRIFT_MM:
                    continue
                if collision_count(new_vertices, new_faces):
                    continue
                change = (name, edge, new_vertices, new_faces, reduction)
                break
            if change is not None:
                break
        if change is None:
            break
        name, edge, vertices, faces, reduction = change
        accepted.append({"kind": name, "edge": list(edge), "bad_reduction": int(reduction)})
    result = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    result.remove_unreferenced_vertices()
    final_bad = int(quality(np.asarray(result.vertices), np.asarray(result.faces))[0].sum())
    topology_ok = result.is_watertight and result.is_winding_consistent and collision_count(
        np.asarray(result.vertices), np.asarray(result.faces)) == 0
    return result, {"status": "quality_and_topology_candidate" if final_bad == 0 and topology_ok else "rejected",
                    "initial_bad_faces": initial_bad, "final_bad_faces": final_bad,
                    "accepted": accepted, "source_constraints": with_source,
                    "topology_ok": bool(topology_ok), "elapsed_ms": (perf_counter() - started) * 1000}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--pamo", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--diagnostics", type=Path, required=True)
    parser.add_argument("--without-source", action="store_true")
    args = parser.parse_args()
    source = trimesh.load(args.source, force="mesh", process=False)
    original = trimesh.load(args.pamo, force="mesh", process=False)
    result, diagnostics = optimize(source, original, not args.without_source)
    args.output.write_text(trimesh.exchange.obj.export_obj(result, digits=17), encoding="utf-8")
    args.diagnostics.write_text(json.dumps(diagnostics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": diagnostics["status"], "initial_bad": diagnostics.get("initial_bad_faces"),
                      "final_bad": diagnostics.get("final_bad_faces")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
