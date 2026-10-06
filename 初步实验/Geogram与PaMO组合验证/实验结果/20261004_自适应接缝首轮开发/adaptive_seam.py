"""细分长约束边，为接缝两侧提供匹配尺度；保持原三角面几何与来源。"""

import numpy as np
import trimesh
from pathlib import Path
import subprocess

from locality_masks import make_masks, save_obj_fp64
from constrained_quality import fixed_surface_contract


def subdivide_constraints(mesh, bits, active, fixed, target, max_splits=10000):
    """共边两侧同步细分；新点位于原边中点，外部面只允许共面细分。"""
    bits, active, fixed = np.asarray(bits).copy(), np.asarray(active, dtype=bool).copy(), np.asarray(fixed, dtype=bool).copy()
    if len(bits) != len(mesh.faces) or len(active) != len(bits) or len(fixed) != len(mesh.vertices):
        raise ValueError("活动域和来源尺寸不一致")
    if not np.isfinite(target) or target <= 0 or np.any(~np.isin(bits, [1, 2])):
        raise ValueError("目标尺度或来源非法")
    vertices, faces = mesh.vertices.copy(), mesh.faces.copy()
    parent_faces = np.arange(len(faces))
    record = {"target_mm": float(target), "max_splits": max_splits, "splits": [],
              "contract": "允许外部共面细分，不再要求外部三角面编号或集合不变"}
    for _ in range(max_splits):
        current = trimesh.Trimesh(vertices, faces, process=False)
        selected = []
        for owners, edge in zip(current.face_adjacency, current.face_adjacency_edges):
            i, j = owners
            if not (active[i] or active[j]):
                continue
            constrained = active[i] != active[j] or bits[i] != bits[j] or np.dot(current.face_normals[i], current.face_normals[j]) < np.cos(np.pi / 4)
            length = np.linalg.norm(vertices[edge[0]] - vertices[edge[1]])
            if constrained and length > 1.25 * target:
                selected.append((float(length), tuple(edge), tuple(owners)))
        if not selected:
            record["budget_exhausted"] = False
            break
        length, (a, b), owners = max(selected)
        midpoint = len(vertices)
        vertices = np.vstack([vertices, (vertices[a] + vertices[b]) / 2])
        fixed = np.append(fixed, True)
        fixed[[a, b]] = True
        additions = []
        for owner in owners:
            face = faces[owner]
            for k in range(3):
                u, v, w = face[k], face[(k + 1) % 3], face[(k + 2) % 3]
                if {int(u), int(v)} == {int(a), int(b)}:
                    faces[owner] = [u, midpoint, w]
                    additions.append([midpoint, v, w])
                    break
        faces = np.vstack([faces, additions])
        bits = np.append(bits, bits[list(owners)])
        active = np.append(active, active[list(owners)])
        parent_faces = np.append(parent_faces, parent_faces[list(owners)])
        record["splits"].append({"edge": [int(a), int(b)], "new_vertex": midpoint, "length_mm": length})
    else:
        record["budget_exhausted"] = True
    result = trimesh.Trimesh(vertices, faces, process=False)
    record["input_faces"] = len(mesh.faces)
    record["output_faces"] = len(faces)
    return result, bits, active, fixed, parent_faces, record


def generate_adaptive_quality(source, bits, tool, directory, executable):
    """先匹配约束边尺度，再沿冻结活动域重网格；整网格安全投影由调用方执行。"""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    active, fixed = make_masks(source, bits, tool, "boolean", 2)
    relevant = np.unique(source.faces[active])
    lengths = source.edges_unique_length[np.all(np.isin(source.edges_unique, relevant), axis=1)]
    target = float(np.median(lengths)) if len(lengths) else float(np.median(source.edges_unique_length))
    prepared, labels, active, fixed, parents, details = subdivide_constraints(source, bits, active, fixed, target)
    if details["budget_exhausted"]:
        raise RuntimeError("接缝细分预算耗尽，不执行部分候选")
    save_obj_fp64(prepared, directory / "source.obj")
    with (directory / "mask.txt").open("w", encoding="utf-8") as stream:
        stream.write(f"{len(prepared.vertices)} {len(prepared.faces)} 1\n")
        stream.writelines(f"{int(v)}\n" for v in fixed)
        stream.writelines(f"{int(a)} {int(b)}\n" for a, b in zip(active, labels))
    run = subprocess.run([str(executable), str(directory / "source.obj"), str(directory / "mask.txt"),
                          str(directory / "remeshed.obj"), str(target), str(directory / "mapping.txt")],
                         capture_output=True, text=True, timeout=300)
    (directory / "remesh.log").write_text(run.stdout + run.stderr, encoding="utf-8")
    if run.returncode:
        raise RuntimeError(f"接缝候选CGAL失败：{run.returncode}")
    result = trimesh.load(directory / "remeshed.obj", force="mesh", process=False)
    lines = (directory / "mapping.txt").read_text().splitlines()
    actual, protected = map(float, lines[0].split())
    mapping = np.array([list(map(int, line.split())) for line in lines[1:]])
    if mapping.shape != (len(result.vertices), 2):
        raise ValueError("候选映射尺寸错误")
    ids, output_fixed = mapping[:, 0], mapping[:, 1].astype(bool)
    retained = (ids >= 0) & output_fixed
    result.vertices[retained] = prepared.vertices[ids[retained]]
    details.update(actual_edge_length_mm=actual, max_protected_edge_mm=protected,
                   fixed_contract=fixed_surface_contract(prepared, result, active, fixed))
    if not details["fixed_contract"]["passed"]:
        raise RuntimeError("共面细分后的外部保持契约失败")
    np.save(directory / "parent_faces.npy", parents)
    return prepared, result, ids, output_fixed, active, fixed, details
