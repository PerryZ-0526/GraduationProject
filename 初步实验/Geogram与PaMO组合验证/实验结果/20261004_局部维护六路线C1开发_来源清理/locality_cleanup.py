"""复用基线的八位坐标去重，保留布尔来源；不删除仍有三个不同顶点的细面。"""

import numpy as np
from scipy.spatial import cKDTree
import trimesh


def clean_provenance(mesh, bits):
    """只移除去重后重复顶点的面，同步筛选标签并检查几何位移预算。"""
    bits = np.asarray(bits)
    if len(bits) != len(mesh.faces) or np.any(~np.isin(bits, [1, 2])):
        raise ValueError("来源缺失或多义，禁止带标签清理")
    clean = trimesh.Trimesh(vertices=mesh.vertices.copy(), faces=mesh.faces.copy(), process=False)
    # 与已有process清理相同的八位坐标键，仅合并顶点，不改变面顺序。
    clean.merge_vertices(digits_vertex=8)
    displacement = float(cKDTree(clean.vertices).query(mesh.vertices)[0].max())
    if displacement > 1e-7:
        raise ValueError("去重位移超过基线1e-7毫米预算")
    faces = clean.faces
    keep = (faces[:, 0] != faces[:, 1]) & (faces[:, 1] != faces[:, 2]) & (faces[:, 2] != faces[:, 0])
    surviving = np.flatnonzero(keep)
    clean.update_faces(keep)
    clean.remove_unreferenced_vertices()
    keys = np.sort(clean.faces, axis=1)
    if len(np.unique(keys, axis=0)) != len(keys):
        raise ValueError("去重产生重复面，来源或绕序可能冲突，停止清理")
    return clean, bits[surviving], {"digits_vertex": 8, "removed_collapsed_faces": int((~keep).sum()),
        "max_raw_vertex_to_clean_vertex_mm": displacement, "surviving_original_face_ids": surviving.tolist(),
        "scope": "仅顶点去重与重复顶点面删除，后续须重审拓扑、来源及独立几何"}
