"""在同来源共面连通区域重新生成三角形，保留闭合边界和孔洞。"""

import numpy as np
import triangle
import trimesh


def interior_point(polygon):
    """扫描顶点高度之间的水平线，取奇偶填充区间内部点，支持凹孔洞。"""
    levels = np.unique(polygon[:, 1])
    best = None
    for low, high in zip(levels, levels[1:]):
        y = (low + high) / 2
        intersections = []
        for a, b in zip(polygon, np.roll(polygon, -1, axis=0)):
            if min(a[1], b[1]) < y < max(a[1], b[1]):
                intersections.append(a[0] + (y - a[1]) * (b[0] - a[0]) / (b[1] - a[1]))
        intersections.sort()
        for a, b in zip(intersections[::2], intersections[1::2]):
            if b > a and (best is None or b - a > best[0]):
                best = (b - a, [(a + b) / 2, y])
    if best is None:
        raise ValueError("孔洞边界没有可判定内部")
    return best[1]


def rebuild_planar_regions(mesh, bits, active, max_regions=200, max_added_per_region=128, allow_shared=False):
    """不跨来源、不改变边界线段；共面误差和区域面积通过后才采用新三角化。"""
    bits, active = np.asarray(bits), np.asarray(active, bool)
    # 共同来源区域单独重建，不与单来源区域合并或改写标签。
    if len(bits) != len(mesh.faces) or len(active) != len(bits) or np.any(~np.isin(bits, [1, 2, 3] if allow_shared else [1, 2])):
        raise ValueError("平面区域来源或活动域非法")
    adjacency = [[] for _ in mesh.faces]
    for a, b in mesh.face_adjacency:
        if bits[a] == bits[b]:
            adjacency[a].append(int(b)); adjacency[b].append(int(a))
    visited = set()
    regions = []
    # 从稳定的大面开始判定支撑平面，避免退化面的零法向决定整个区域。
    for seed in np.argsort(-mesh.area_faces, kind="stable"):
        seed = int(seed)
        if seed in visited or mesh.area_faces[seed] <= 1e-12:
            continue
        normal, origin = mesh.face_normals[seed], mesh.triangles[seed, 0]
        region, frontier = [], [seed]
        while frontier:
            face = frontier.pop()
            if face in visited:
                continue
            if np.max(np.abs((mesh.triangles[face] - origin) @ normal)) > 1e-10:
                continue
            if mesh.area_faces[face] > 1e-12 and mesh.face_normals[face] @ normal < 1 - 1e-10:
                continue
            visited.add(face); region.append(face)
            frontier.extend(adjacency[face])
        if len(region) >= 2 and active[region].any():
            regions.append((region, normal, origin))
    vertices = mesh.vertices.tolist()
    support_normals = [[0.0, 0.0, 0.0] for _ in vertices]
    support_origins = [[0.0, 0.0, 0.0] for _ in vertices]
    removed, additions, labels = set(), [], []
    record = {"plane_tolerance_mm": 1e-10, "max_regions": max_regions, "max_added_per_region": max_added_per_region,
              "triangle_options": f"pYYq20S{max_added_per_region}Q", "regions": [], "eligible_regions": len(regions)}
    for region, normal, origin in regions[:max_regions]:
        edges = {}
        for face in mesh.faces[region]:
            for a, b in zip(face, np.roll(face, -1)):
                key = tuple(sorted((int(a), int(b))))
                edges.setdefault(key, []).append((int(a), int(b)))
        boundary = [directions[0] for directions in edges.values() if len(directions) == 1]
        outgoing = {}
        incoming = {}
        for a, b in boundary:
            outgoing.setdefault(a, []).append(b); incoming.setdefault(b, []).append(a)
        details = {"input_faces": len(region), "source_bit": int(bits[region[0]]), "accepted": False}
        record["regions"].append(details)
        if not boundary or any(len(v) != 1 for v in outgoing.values()) or set(outgoing) != set(incoming) or any(len(v) != 1 for v in incoming.values()):
            details["rejection"] = "边界不是互不相交闭环"
            continue
        loops, remaining = [], set(outgoing)
        while remaining:
            start = min(remaining); current = start; loop = []
            while current in remaining:
                loop.append(current); remaining.remove(current); current = outgoing[current][0]
            if current != start:
                break
            loops.append(loop)
        if remaining or not loops or sum(map(len, loops)) != len(boundary):
            details["rejection"] = "边界闭环遍历失败"
            continue
        ids = sorted(outgoing)
        tangent = mesh.vertices[boundary[0][1]] - mesh.vertices[boundary[0][0]]
        length = np.linalg.norm(tangent)
        if length <= 1e-14:
            details["rejection"] = "零长度边界"
            continue
        tangent /= length
        bitangent = np.cross(normal, tangent)
        coordinates = np.column_stack([(mesh.vertices[ids] - origin) @ tangent, (mesh.vertices[ids] - origin) @ bitangent])
        lookup = {v: i for i, v in enumerate(ids)}
        holes = []
        for loop in loops:
            polygon = coordinates[[lookup[v] for v in loop]]
            signed = np.sum(polygon[:, 0] * np.roll(polygon[:, 1], -1) - polygon[:, 1] * np.roll(polygon[:, 0], -1)) / 2
            if signed < 0:
                holes.append(interior_point(polygon))
        request = {"vertices": coordinates, "segments": np.array([[lookup[a], lookup[b]] for a, b in boundary])}
        if holes:
            request["holes"] = np.asarray(holes)
        generated = triangle.triangulate(request, record["triangle_options"])
        if "triangles" not in generated or not np.array_equal(generated["vertices"][:len(ids)], coordinates):
            details["rejection"] = "三角化缺失或原边界点被改写"
            continue
        points = generated["vertices"]
        lifted = origin + points[:, :1] * tangent + points[:, 1:] * bitangent
        lifted[:len(ids)] = mesh.vertices[ids]
        faces = generated["triangles"]
        triangles = lifted[faces]
        normals = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
        if np.any(normals @ normal <= 0):
            details["rejection"] = "新面退化或反向"
            continue
        area = float(np.linalg.norm(normals, axis=1).sum() / 2)
        old_area = float(mesh.area_faces[region].sum())
        if abs(area - old_area) > 1e-9 * max(1, old_area):
            details["rejection"] = "区域面积不一致"
            continue
        new_edges = np.sort(np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]]), axis=1)
        unique, counts = np.unique(new_edges, axis=0, return_counts=True)
        if {tuple(e) for e in unique[counts == 1]} != {tuple(sorted((lookup[a], lookup[b]))) for a, b in boundary}:
            details["rejection"] = "原始边界线段未完整保留"
            continue
        mapping = np.array(ids + list(range(len(vertices), len(vertices) + len(points) - len(ids))))
        vertices.extend(lifted[len(ids):].tolist())
        support_normals.extend([normal.tolist()] * (len(points) - len(ids)))
        support_origins.extend([origin.tolist()] * (len(points) - len(ids)))
        additions.extend(mapping[faces].tolist())
        labels.extend([int(bits[region[0]])] * len(faces))
        removed.update(region)
        details.update(accepted=True, output_faces=len(faces), added_vertices=len(points) - len(ids), holes=len(holes), area_difference_mm2=area - old_area)
    keep = np.array([i not in removed for i in range(len(mesh.faces))])
    faces = np.vstack([mesh.faces[keep], np.array(additions, dtype=int).reshape(-1, 3)])
    used, inverse = np.unique(faces, return_inverse=True)
    result = trimesh.Trimesh(np.array(vertices)[used], inverse.reshape(-1, 3), process=False)
    record["budget_exhausted"] = len(regions) > max_regions
    record["vertex_original_ids"] = np.where(used < len(mesh.vertices), used, -1).tolist()
    record["vertex_support_normals"] = np.asarray(support_normals)[used].tolist()
    record["vertex_support_origins"] = np.asarray(support_origins)[used].tolist()
    return result, np.concatenate([bits[keep], np.array(labels, dtype=bits.dtype)]), record
