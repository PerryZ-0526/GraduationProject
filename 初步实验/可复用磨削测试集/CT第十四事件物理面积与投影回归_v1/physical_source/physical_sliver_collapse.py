"""按闭合链接条件与逐面平面约束折叠退化碎片，不采用QEM质量收益主张。"""

import numpy as np
import trimesh
from fractions import Fraction

# 使用同一诊断副本的物理面积判据。


def exact_unit_normal(triangle):
    """在极小面上以实际二进制坐标的有理数叉积取得支撑平面方向。"""
    points=[[Fraction(float(x)) for x in p] for p in triangle]
    a=[points[1][k]-points[0][k] for k in range(3)]
    b=[points[2][k]-points[0][k] for k in range(3)]
    cross=[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]
    scale=max(abs(x) for x in cross)
    if scale==0:
        return None
    normal=np.array([float(x/scale) for x in cross])
    return normal/np.linalg.norm(normal)


def collapse_degenerate(mesh, bits, allow_shared=False, allow_small_incident=False):
    """仅折叠退化面关联边，每次严格减少FP64或FP32退化面。"""
    bits = np.asarray(bits)
    # 新开发允许位3原样传播，折叠后每个保留面仍继承其原标签。
    if len(bits) != len(mesh.faces) or np.any(~np.isin(bits, [1, 2, 3] if allow_shared else [1, 2])):
        raise ValueError("来源缺失或多义，禁止碎片折叠")
    vertices, faces = mesh.vertices.copy(), mesh.faces.copy()
    source_bits = bits.copy()
    initial = int(invalid_faces(vertices, faces).sum())
    record = {"initial_invalid_faces": initial, "max_collapses": initial, "plane_tolerance_mm": 1e-8,
              "collapses": [], "allow_small_incident":allow_small_incident,
              "scope": "数值链接和逐面平面检查，后续必须重审整网格与来源"}
    for _ in range(initial):
        bad = invalid_faces(vertices, faces)
        pairs = np.sort(np.concatenate([faces[bad][:, [0, 1]], faces[bad][:, [1, 2]], faces[bad][:, [2, 0]]]), axis=1)
        edges = np.unique(pairs, axis=0)
        order = np.argsort(np.linalg.norm(vertices[edges[:, 0]] - vertices[edges[:, 1]], axis=1), kind="stable")
        accepted = False
        for edge in edges[order]:
            a, b = map(int, edge)
            shared = np.sum(np.isin(faces, [a, b]), axis=1) == 2
            if int(shared.sum()) != 2:
                continue
            neighbors_a = set(faces[np.any(faces == a, axis=1)].ravel()) - {a}
            neighbors_b = set(faces[np.any(faces == b, axis=1)].ravel()) - {b}
            opposites = set(faces[shared].ravel()) - {a, b}
            if neighbors_a & neighbors_b != opposites:
                continue
            for remove, retain in ((a, b), (b, a)):
                incident = np.any(faces == remove, axis=1)
                changed = incident & ~shared
                old = vertices[faces[changed]]
                normals = np.cross(old[:, 1] - old[:, 0], old[:, 2] - old[:, 0])
                lengths = np.linalg.norm(normals, axis=1)
                if not len(lengths) or (not allow_small_incident and np.any(lengths <= 2e-12)):
                    continue
                # 新显式机制允许相邻小面参与同一修复链，精确共线面仍拒绝。
                small=lengths <= 2e-12
                if allow_small_incident and small.any():
                    stable=[exact_unit_normal(t) for t in old[small]]
                    if any(n is None for n in stable):
                        continue
                    normals[~small] /= lengths[~small,None]
                    normals[small] = np.asarray(stable)
                else:
                    normals /= lengths[:, None]
                deviation = np.abs(np.sum((vertices[retain] - old[:, 0]) * normals, axis=1))
                if np.any(deviation > 1e-8):
                    continue
                replacement = faces.copy()
                replacement[replacement == remove] = retain
                keep = ~shared
                new_faces = replacement[keep]
                if len(np.unique(np.sort(new_faces, axis=1), axis=0)) != len(new_faces):
                    continue
                new = vertices[replacement[changed]]
                new_normals = np.cross(new[:, 1] - new[:, 0], new[:, 2] - new[:, 0])
                # 小面可以暂时仍小，但不反向；最终整网格门槛不变，且每步坏面数严格下降。
                orientation_budget=np.where(small,0.0,2e-12) if allow_small_incident else 2e-12
                if np.any(np.sum(new_normals * normals, axis=1) <= orientation_budget):
                    continue
                changed_bad=invalid_faces(vertices,replacement[changed])
                introduced_bad=changed_bad & ~bad[changed] if allow_small_incident else changed_bad
                if introduced_bad.any() or int(invalid_faces(vertices, new_faces).sum()) >= int(bad.sum()):
                    continue
                faces = new_faces
                source_bits = source_bits[keep]
                record["collapses"].append({"removed_vertex": remove, "retained_vertex": retain,
                    "endpoint_distance_mm": float(np.linalg.norm(vertices[remove] - vertices[retain])),
                    "max_incident_plane_deviation_mm": float(deviation.max()), "deleted_faces": int(shared.sum())})
                accepted = True
                break
            if accepted:
                break
        if not accepted:
            break
    result = trimesh.Trimesh(vertices, faces, process=False)
    result.remove_unreferenced_vertices()
    record["remaining_invalid_faces"] = int(invalid_faces(result.vertices, result.faces).sum())
    return result, source_bits, record
