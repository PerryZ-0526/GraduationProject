"""逐面支撑的外舍入区间证明；边界不确定时仍用精确有理数核查。"""
from fractions import Fraction
import numpy as np


def certify_face_support_interval(mesh, normals, offsets, selected):
    """逐面三顶点全部核查，快速证明不确定的点对不省略。"""
    vertices = np.asarray(mesh.vertices, np.float64)
    faces = np.asarray(mesh.faces, np.int64)
    normals = np.asarray(normals, np.float64)
    offsets = np.asarray(offsets, np.float64)
    selected = np.asarray(selected, np.int64)
    if selected.shape != (len(faces),) or normals.shape != (len(offsets), 3):
        raise ValueError('整面支撑分配或支撑平面尺寸不符')
    if not all(np.isfinite(values).all() for values in (vertices, normals, offsets)):
        raise ValueError('支撑证明输入必须有限')
    pairs = np.column_stack((np.repeat(selected, 3), faces.reshape(-1)))
    unique, inverse = np.unique(pairs, axis=0, return_inverse=True)
    points, directions = vertices[unique[:, 1]], normals[unique[:, 0]]
    lower, upper = np.zeros(len(unique)), np.zeros(len(unique))
    with np.errstate(over='ignore', under='ignore', invalid='ignore'):
        for axis in range(3):
            # 显式逐项乘法与加法外舍入，不使用BLAS或融合乘加近似证明。
            product = points[:, axis] * directions[:, axis]
            lower = np.nextafter(lower + np.nextafter(product, -np.inf), -np.inf)
            upper = np.nextafter(upper + np.nextafter(product, np.inf), np.inf)
    right = offsets[unique[:, 0]]
    finite = np.isfinite(lower) & np.isfinite(upper)
    passed = finite & (lower >= right)
    rejected = finite & (upper < right)
    uncertain = ~(passed | rejected)
    exact_normals, exact_vertices, exact_offsets = {}, {}, {}
    for index in np.flatnonzero(uncertain):
        plane, vertex = map(int, unique[index])
        if plane not in exact_normals:
            exact_normals[plane] = tuple(Fraction(float(x)) for x in normals[plane])
            exact_offsets[plane] = Fraction(float(offsets[plane]))
        if vertex not in exact_vertices:
            exact_vertices[vertex] = tuple(Fraction(float(x)) for x in vertices[vertex])
        value = sum(a * b for a, b in zip(exact_normals[plane], exact_vertices[vertex]))
        passed[index] = value >= exact_offsets[plane]
    failed = np.flatnonzero(~passed[inverse].reshape((-1, 3)).all(axis=1))
    return {'passed': len(failed) == 0, 'failed_face_count': len(failed), 'failed_face_ids': failed[:20].tolist(),
            'certified_scope': '全部三角面避开外舍入支撑半空间交集的内部；不认证网格嵌入性或整体Hausdorff距离',
            'interval_pair_count': int((~uncertain).sum()), 'exact_fallback_pair_count': int(uncertain.sum()),
            'all_face_vertices_checked': True}
