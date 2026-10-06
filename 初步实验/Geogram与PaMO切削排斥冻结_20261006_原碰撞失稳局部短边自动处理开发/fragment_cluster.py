"""整组消除FP32同坐标数值碎片；整网格与几何审计失败时回滚。"""

import numpy as np
import trimesh
from geometry_preservation_audit import mesh_valid, MeshDistance
from audit_pamo_outputs import as_polydata
from locality_retriangulate import invalid_faces


def repair_fp32_clusters(mesh, bits):
    """仅处理实际退化面关联的同FP32坐标组，代表点取原有顶点。"""
    bits = np.asarray(bits)
    if len(bits) != len(mesh.faces) or np.any(~np.isin(bits, [1, 2])) or not np.isfinite(mesh.vertices).all():
        raise ValueError("碎片簇输入或来源非法")
    bad = invalid_faces(mesh.vertices, mesh.faces)
    record = {"initial_invalid_faces": int(bad.sum()), "groups": [], "accepted": False,
              "geometry_budget_mm": 1e-7, "continuous_geometry_certified": False}
    _, inverse, counts = np.unique(mesh.vertices.astype(np.float32), axis=0, return_inverse=True, return_counts=True)
    incident_groups = np.unique(inverse[np.unique(mesh.faces[bad])])
    mapping = np.arange(len(mesh.vertices))
    for group in incident_groups:
        if counts[group] < 2:
            continue
        vertices = np.flatnonzero(inverse == group)
        points = mesh.vertices[vertices]
        distances = np.linalg.norm(points[:, None] - points[None, :], axis=2)
        representative = int(vertices[np.argmin(distances.max(axis=1))])
        deviation = float(np.linalg.norm(points - mesh.vertices[representative], axis=1).max())
        if deviation > 1e-7:
            continue
        mapping[vertices] = representative
        record["groups"].append({"vertices": vertices.tolist(), "representative": representative, "max_movement_mm": deviation})
    faces = mapping[mesh.faces]
    keep = (faces[:, 0] != faces[:, 1]) & (faces[:, 1] != faces[:, 2]) & (faces[:, 2] != faces[:, 0])
    faces, labels = faces[keep], bits[keep]
    if len(np.unique(np.sort(faces, axis=1), axis=0)) != len(faces) or len(faces) == 0:
        record["rejection"] = "合并产生重复面或空实体"
        return mesh.copy(), bits.copy(), record
    vertices, index = np.unique(faces, return_inverse=True)
    candidate = trimesh.Trimesh(mesh.vertices[vertices], index.reshape(-1, 3), process=False)
    valid, checks = mesh_valid(candidate)
    remaining = int(invalid_faces(candidate.vertices, candidate.faces).sum())
    same_topology = (candidate.euler_number == mesh.euler_number and len(candidate.split(only_watertight=False)) == len(mesh.split(only_watertight=False)))
    forward = MeshDistance(as_polydata(mesh))(np.vstack([candidate.vertices, candidate.triangles_center]))
    reverse = MeshDistance(as_polydata(candidate))(np.vstack([mesh.vertices, mesh.triangles_center]))
    probe = max(float(forward.max(initial=0)), float(reverse.max(initial=0)))
    record.update(remaining_invalid_faces=remaining, audit=checks, same_topology=bool(same_topology), geometry_probe_max_mm=probe,
                  removed_faces=int((~keep).sum()), accepted=bool(valid and same_topology and remaining == 0 and probe <= 1e-7))
    return (candidate, labels, record) if record["accepted"] else (mesh.copy(), bits.copy(), record)
