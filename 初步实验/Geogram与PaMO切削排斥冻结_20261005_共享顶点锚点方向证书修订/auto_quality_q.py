"""从完整PaMO网格选择受约束操作；默认优化小角尾部，旧目标可显式复现。"""

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


def source_features(mesh: trimesh.Trimesh) -> tuple:
    """从Geogram面邻接提取锐边；不把它直接解释为真实CSG交线。"""
    pairs = mesh.face_adjacency
    dots = np.einsum("ij,ij->i", mesh.face_normals[pairs[:, 0]], mesh.face_normals[pairs[:, 1]])
    selected = mesh.face_adjacency_edges[dots < np.cos(np.deg2rad(60))]
    segments = np.asarray(mesh.vertices[selected], dtype=np.float64)
    centers = segments.mean(axis=1) if len(segments) else np.empty((0, 3))
    half_length = (float(np.max(np.linalg.norm(segments[:, 1] - segments[:, 0], axis=1))) / 2
                   if len(segments) else 0.0)
    return segments, centers, cKDTree(centers) if len(centers) else None, half_length


def edge_feature_state(a: np.ndarray, b: np.ndarray, features: tuple) -> str:
    """返回保护、非特征或多义；多义边不操作。"""
    segments, centers, tree, half_length = features
    if tree is None:
        return "smooth"
    midpoint = (a + b) / 2
    # 检索半径覆盖来源锐边的半长；该值在输入阶段预先计算。
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


def vertex_manifold_closed(faces: np.ndarray) -> bool:
    """每个顶点的邻接面必须形成单个闭合环，拒绝仅共顶点的多片表面。"""
    links = {}
    for a, b, c in faces:
        for center, first, second in ((a, b, c), (b, c, a), (c, a, b)):
            ring = links.setdefault(int(center), {})
            ring.setdefault(int(first), set()).add(int(second))
            ring.setdefault(int(second), set()).add(int(first))
    for ring in links.values():
        if not ring or any(len(neighbors) != 2 for neighbors in ring.values()):
            return False
        start = next(iter(ring))
        visited = {start}
        frontier = [start]
        while frontier:
            current = frontier.pop()
            for neighbor in ring[current] - visited:
                visited.add(neighbor)
                frontier.append(neighbor)
        if len(visited) != len(ring):
            return False
    return True


def valid_closed_input(mesh: trimesh.Trimesh, expected_components: int) -> bool:
    """入口同时拒绝无穷值、退化面、错误绕序和不符预期的实体拓扑。"""
    return bool(
        np.isfinite(mesh.vertices).all() and
        np.isfinite(mesh.faces).all() and
        np.all(mesh.area_faces > 1e-12) and
        mesh.is_watertight and mesh.is_winding_consistent and mesh.volume > 0 and
        vertex_manifold_closed(np.asarray(mesh.faces)) and
        len(mesh.split(only_watertight=False)) == expected_components
    )


def source_match(source: trimesh.Trimesh, vertices: np.ndarray,
                 faces: np.ndarray, affected: np.ndarray) -> bool:
    """联合检查改动面中心到来源面的距离与同向性。"""
    triangles = vertices[faces[affected]]
    centers = triangles.mean(axis=1)
    _, distances, source_faces = trimesh.proximity.closest_point(source, centers)
    normals = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    lengths = np.linalg.norm(normals, axis=1)
    normals = np.divide(normals, lengths[:, None], out=np.zeros_like(normals),
                        where=lengths[:, None] > 0)
    alignment = np.einsum("ij,ij->i", normals, source.face_normals[source_faces])
    return bool(np.all(distances <= MAX_SOURCE_DRIFT_MM) and np.all(alignment >= 0.5))


def flip_candidate(vertices: np.ndarray, faces: np.ndarray, edge: tuple[int, int],
                   owners: list[int], objective: str = "legacy"):
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
    if any(not np.isfinite((area, q, angle)).all() or area <= 1e-12
           for area, q, angle, _ in after):
        return None
    if objective == "tail":
        old_tail = tuple(sum(value[2] < threshold for value in before)
                         for threshold in (1, 5, 10))
        new_tail = tuple(sum(value[2] < threshold for value in after)
                         for threshold in (1, 5, 10))
        if any(new > old for old, new in zip(old_tail, new_tail)) or old_tail == new_tail:
            return None
        reduction = sum(old - new for old, new in zip(old_tail, new_tail))
    else:
        old_bad = sum(area <= 1e-12 or q < 0.4 or angle < 25 for area, q, angle, _ in before)
        new_bad = sum(area <= 1e-12 or q < 0.4 or angle < 25 for area, q, angle, _ in after)
        if new_bad >= old_bad:
            return None
        reduction = old_bad - new_bad
    normal = before[0][3] + before[1][3]
    normal /= np.linalg.norm(normal)
    if any(value[3] @ normal <= 0.9 for value in after):
        return None
    proposed = faces.copy()
    proposed[[first_id, second_id]] = replacement
    return vertices, proposed, reduction


def collapse_candidates(source: trimesh.Trimesh, vertices: np.ndarray, faces: np.ndarray,
                        edge: tuple[int, int], incident: dict, neighbors: dict,
                        parents: list[set[int]], original_vertices: np.ndarray):
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
        # 合并点同时约束全部祖先顶点，防止多次折叠重置累计位移预算。
        ancestors = sorted(parents[first] | parents[second])
        if np.max(np.linalg.norm(original_vertices[ancestors] - point, axis=1)) > MAX_MOVE_MM:
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


def optimize(source: trimesh.Trimesh, original: trimesh.Trimesh,
             with_source: bool = True, expected_components: int = 1,
             objective: str = "tail") -> tuple:
    """有限次数评估局部操作；结果仍需独立审计。"""
    started = perf_counter()
    vertices = np.asarray(original.vertices, dtype=np.float64).copy()
    original_vertices = vertices.copy()
    faces = np.asarray(original.faces, dtype=np.int64).copy()
    parents = [{index} for index in range(len(vertices))]
    if (not valid_closed_input(source, expected_components) or
            collision_count(np.asarray(source.vertices), np.asarray(source.faces))):
        return original, {"status": "rejected_source_input", "accepted": []}
    if not valid_closed_input(original, expected_components):
        return original, {"status": "rejected_pamo_input_topology", "accepted": []}
    # 消融分支以原PaMO快照作几何参照，保持投影算子与预算，移除Geogram来源约束。
    constraint_surface = source if with_source else original
    features = source_features(source) if with_source else (
        np.empty((0, 2, 3)), np.empty((0, 3)), None, 0.0)
    if collision_count(vertices, faces):
        return original, {"status": "rejected_input_self_intersection", "accepted": []}
    initial_bad = int(quality(vertices, faces)[0].sum())
    initial_angles = quality(vertices, faces)[2]
    initial_tail = {str(threshold): int(np.count_nonzero(initial_angles < threshold))
                    for threshold in (1, 5, 10)}
    accepted = []
    for _ in range(min(initial_tail["10"] if objective == "tail" else initial_bad,
                       MAX_ACCEPTED)):
        bad, _, angles = quality(vertices, faces)
        if objective == "tail":
            bad = angles < 10
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
            flipped = flip_candidate(vertices, faces, edge, edge_owners[edge], objective)
            if flipped is not None and tuple(sorted(set(faces[edge_owners[edge]].ravel()) - set(edge))) not in edge_owners:
                proposals.append(("flip", *flipped, None))
            if objective == "legacy" and old_length <= MAX_EDGE_MM:
                proposals.extend(("collapse", *item) for item in collapse_candidates(
                    constraint_surface, vertices, faces, edge, incident, neighbors,
                    parents, original_vertices))
            for name, new_vertices, new_faces, reduction, point in proposals:
                affected = (np.asarray(edge_owners[edge], dtype=np.int64) if name == "flip"
                            else np.flatnonzero(np.any(new_faces == edge[0], axis=1)))
                if not source_match(constraint_surface, new_vertices, new_faces, affected):
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
        if name == "collapse":
            parents[edge[0]].update(parents[edge[1]])
        accepted.append({"kind": name, "edge": list(edge),
                         ("tail_reduction" if objective == "tail" else "bad_reduction"):
                             int(reduction)})
    referenced = np.unique(faces)
    max_cumulative_move = max(
        (float(np.max(np.linalg.norm(original_vertices[sorted(parents[index])] - vertices[index], axis=1)))
         for index in referenced), default=0.0)
    result = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    result.remove_unreferenced_vertices()
    final_bad = int(quality(np.asarray(result.vertices), np.asarray(result.faces))[0].sum())
    final_angles = quality(np.asarray(result.vertices), np.asarray(result.faces))[2]
    final_tail = {str(threshold): int(np.count_nonzero(final_angles < threshold))
                  for threshold in (1, 5, 10)}
    topology_ok = (result.is_watertight and result.is_winding_consistent and
                   vertex_manifold_closed(np.asarray(result.faces)) and
                   len(result.split(only_watertight=False)) == expected_components and collision_count(
        np.asarray(result.vertices), np.asarray(result.faces)) == 0
                   )
    return result, {"status": "independent_audit_pending" if topology_ok else "rejected",
                    "objective": objective,
                    "initial_bad_faces": initial_bad, "final_bad_faces": final_bad,
                    "initial_tail_faces": initial_tail, "final_tail_faces": final_tail,
                    "accepted": accepted, "source_constraints": with_source,
                    "topology_ok": bool(topology_ok),
                    "max_cumulative_parent_move_mm": max_cumulative_move,
                    "elapsed_ms": (perf_counter() - started) * 1000}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--pamo", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--diagnostics", type=Path, required=True)
    parser.add_argument("--without-source", action="store_true")
    parser.add_argument("--objective", choices=("tail", "legacy"), default="tail")
    parser.add_argument("--expected-components", type=int, default=1)
    args = parser.parse_args()
    source = trimesh.load(args.source, force="mesh", process=False)
    original = trimesh.load(args.pamo, force="mesh", process=False)
    result, diagnostics = optimize(source, original, not args.without_source,
                                   args.expected_components, args.objective)
    args.output.write_text(trimesh.exchange.obj.export_obj(result, digits=17), encoding="utf-8")
    args.diagnostics.write_text(json.dumps(diagnostics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": diagnostics["status"], "initial_bad": diagnostics.get("initial_bad_faces"),
                      "final_bad": diagnostics.get("final_bad_faces")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
