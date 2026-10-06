"""默认共面简化后的缺失来源仅在操作数几何唯一匹配时恢复。"""

import numpy as np

from locality_diagnostic import SurfaceQuery


def recover_sources(mesh, bits, parent, tool):
    """核对全部面顶点与面心；缺失标签双匹配或无匹配时明确拒绝。"""
    bits = np.asarray(bits)
    if len(bits) != len(mesh.faces) or np.any(~np.isin(bits, [0, 1, 2])):
        raise ValueError("来源数组长度或取值无效")
    samples = np.concatenate((mesh.triangles, mesh.triangles_center[:, None]), axis=1).reshape(-1, 3)
    parent_distance = SurfaceQuery(parent)(samples)[0].reshape(-1, 4).max(axis=1)
    tool_distance = SurfaceQuery(tool)(samples)[0].reshape(-1, 4).max(axis=1)
    parent_match, tool_match = parent_distance <= 1e-8, tool_distance <= 1e-8
    if np.any((bits == 1) & ~parent_match | (bits == 2) & ~tool_match):
        raise ValueError("已有来源标签与所属操作数几何不符")
    missing = bits == 0
    inferred = parent_match.astype(int) + 2 * tool_match.astype(int)
    if np.any(missing & ~np.isin(inferred, [1, 2])):
        raise ValueError("缺失来源存在双匹配或无匹配，禁止强行恢复")
    recovered = bits.copy()
    recovered[missing] = inferred[missing]
    return recovered, {"missing_faces": int(missing.sum()), "uniquely_recovered_faces": int(missing.sum()),
        "distance_tolerance_mm": 1e-8, "samples_per_face": 4,
        "scope": "顶点与面心数值唯一匹配，不是精确来源或连续几何证书"}
