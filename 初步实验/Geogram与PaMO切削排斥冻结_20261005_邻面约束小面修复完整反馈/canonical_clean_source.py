"""规范排序已清理布尔源，不焊接、舍入、删除面或改变来源。"""

import numpy as np
import trimesh


def canonical_clean_source(mesh, bits):
    """顶点按坐标排序，有向面仅循环换起点，来源随原面同步重排。"""
    bits = np.asarray(bits)
    if len(bits) != len(mesh.faces) or not np.isfinite(mesh.vertices).all():
        raise ValueError("布尔源非有限或来源长度不同")
    order = np.lexsort((mesh.vertices[:, 2], mesh.vertices[:, 1], mesh.vertices[:, 0]))
    coordinates = mesh.vertices[order]
    # 本入口需要已焊接输入；重复坐标仍代表不同拓扑点时，不能按旧编号偷偷破平局。
    if np.any(np.all(coordinates[1:] == coordinates[:-1], axis=1)):
        raise ValueError("已清理源仍有重复坐标，不能保证与旧编号无关的规范表示")
    inverse = np.empty(len(order), dtype=int)
    inverse[order] = np.arange(len(order))
    faces = inverse[mesh.faces]
    starts = faces.argmin(axis=1)
    faces = np.take_along_axis(faces, (starts[:, None] + np.arange(3)) % 3, axis=1)
    face_order = np.lexsort((bits, faces[:, 2], faces[:, 1], faces[:, 0]))
    result = trimesh.Trimesh(coordinates.copy(), faces[face_order].copy(), process=False)
    return result, bits[face_order].copy(), {"old_vertex_ids": order.tolist(),
        "old_face_ids": face_order.tolist(), "cyclic_start_by_old_face": starts.tolist(),
        "coordinates_changed": False, "faces_removed": 0, "source_labels_changed": False}
