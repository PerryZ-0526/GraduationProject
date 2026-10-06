"""根据本次布尔来源或普通空间邻域生成活动面和固定顶点。"""

import numpy as np


def save_obj_fp64(mesh, path):
    """采用17位有效数字而非固定小数位，保证极小FP64坐标可原样重载。"""
    with open(path, "w", encoding="utf-8", newline="\n") as stream:
        for x, y, z in mesh.vertices:
            stream.write(f"v {x:.17g} {y:.17g} {z:.17g}\n")
        for a, b, c in mesh.faces:
            stream.write(f"f {a + 1} {b + 1} {c + 1}\n")


def expand_faces(mesh, core, rings):
    active = np.asarray(core, dtype=bool).copy()
    pairs = mesh.face_adjacency
    for _ in range(rings):
        connected = np.any(active[pairs], axis=1)
        active[np.unique(pairs[connected])] = True
    return active


def make_masks(mesh, bits, tool, mode, rings=2):
    """所有触及非活动面的顶点固定，含活动域边界的完整一圈顶点。"""
    if mode == "global":
        active = np.ones(len(mesh.faces), dtype=bool)
    elif mode == "boolean":
        bits = np.asarray(bits)
        if len(bits) != len(mesh.faces) or np.any(~np.isin(bits, [1, 2])):
            raise ValueError("布尔来源缺失或多义")
        core = bits == 2
        pairs = mesh.face_adjacency
        seam = bits[pairs[:, 0]] != bits[pairs[:, 1]]
        core[np.unique(pairs[seam])] = True
        active = expand_faces(mesh, core, rings)
    elif mode == "spatial":
        # 普通基线仅用工具包围盒，不读取来源、交线或评价答案。
        bounds = tool.bounds + np.array([[-0.1] * 3, [0.1] * 3])
        core = np.all(mesh.triangles.max(axis=1) >= bounds[0], axis=1) & np.all(
            mesh.triangles.min(axis=1) <= bounds[1], axis=1)
        active = expand_faces(mesh, core, rings)
    else:
        raise ValueError("未知活动域模式")
    fixed = np.zeros(len(mesh.vertices), dtype=bool)
    fixed[np.unique(mesh.faces[~active])] = True
    return active, fixed


def external_contract(source, candidate, original_ids, active, fixed):
    """通过原始顶点映射核对外部面集合和固定顶点的精确坐标。"""
    original_ids = np.asarray(original_ids)
    if len(original_ids) != len(candidate.vertices) or len(np.unique(original_ids)) != len(original_ids):
        return {"passed": False, "reason": "顶点对应映射无效"}
    def oriented_key(face):
        # 循环重排不改变绕序，反向三角面不能冒充原外部面。
        a, b, c = map(int, face)
        return min((a, b, c), (b, c, a), (c, a, b))

    before = {oriented_key(f) for f in source.faces[~active]}
    mapped = original_ids[candidate.faces]
    after = {oriented_key(f) for f in mapped if np.all(fixed[f])}
    # 固定顶点组成的活动面也可能保留，仅要求所有外部面在输出仍存在。
    external_present = before <= after
    selected = fixed[original_ids]
    fixed_present = np.all(np.isin(np.flatnonzero(fixed), original_ids))
    exact = np.array_equal(candidate.vertices[selected], source.vertices[original_ids[selected]])
    return {"passed": bool(external_present and fixed_present and exact),
            "external_faces": len(before), "external_faces_retained": len(before & after),
            "all_fixed_vertices_retained": bool(fixed_present), "fixed_positions_exact": bool(exact)}
