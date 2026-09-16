"""通过投影多边形交叠检查局部面，并计算两张分片线性高度面的误差极值。"""
import numpy as np


def cross2(a, b):
    return a[..., 0]*b[..., 1]-a[..., 1]*b[..., 0]


def polygon_area(polygon):
    if len(polygon) < 3:
        return 0.
    return float(abs(np.sum(cross2(polygon, np.roll(polygon, -1, axis=0))))/2)


def clip_polygon(subject, clip):
    """凸多边形逆时针半平面裁剪；容差只处理浮点共边，不使用平滑修补。"""
    polygon = np.asarray(subject, dtype=float)
    for a, b in zip(clip, np.roll(clip, -1, axis=0)):
        if len(polygon) == 0:
            break
        distance = cross2(b-a, polygon-a)
        result = []
        for i in range(len(polygon)):
            previous = (i-1) % len(polygon)
            current_inside, previous_inside = distance[i] >= -1e-12, distance[previous] >= -1e-12
            if current_inside != previous_inside:
                fraction = distance[previous]/(distance[previous]-distance[i])
                result.append(polygon[previous]+fraction*(polygon[i]-polygon[previous]))
            if current_inside:
                result.append(polygon[i])
        polygon = np.asarray(result).reshape(-1, 2)
    return polygon


def triangle_height(triangle, xy):
    """在原三角面平面上插值高度，不重新拟合或平滑原始CT面。"""
    gradient = np.linalg.solve(triangle[1:, :2]-triangle[0, :2], triangle[1:, 2]-triangle[0, 2])
    return triangle[0, 2]+(xy-triangle[0, :2]) @ gradient


def verify_chart(surface, half_width):
    """固定解剖高度窗与法向门槛，仅在覆盖、无重叠及无遮挡均通过后认可图面。"""
    domain = np.array([[-half_width, -half_width], [half_width, -half_width],
                       [half_width, half_width], [-half_width, half_width]])
    triangles = surface.triangles
    candidates = list(surface.tree.intersection((-half_width, -half_width, half_width, half_width)))
    selected = [i for i in candidates if triangles[i, :, 2].min() >= -2 and
                triangles[i, :, 2].max() <= 3 and surface.mesh.face_normals[i, 2] >= .5]
    polygons = {i: clip_polygon(triangles[i, :, :2], domain) for i in selected}
    polygons = {i: p for i, p in polygons.items() if polygon_area(p) > 1e-10}
    selected = set(polygons)
    overlaps, occlusions = [], []
    for i, polygon in polygons.items():
        bbox = (*polygon.min(axis=0), *polygon.max(axis=0))
        for j in surface.tree.intersection(bbox):
            if j == i or (j in selected and j < i):
                continue
            other = triangles[j, :, :2]
            if surface.det[j] < 0:
                other = other[::-1]
            overlap = clip_polygon(polygon, other)
            if polygon_area(overlap) <= 1e-9:
                continue
            if j in selected:
                overlaps.append([int(i), int(j)])
            elif np.max(triangle_height(triangles[j], overlap)-triangle_height(triangles[i], overlap)) > 1e-6:
                occlusions.append([int(i), int(j)])
    covered = sum(polygon_area(p) for p in polygons.values())
    faces = surface.mesh.faces[list(polygons)]
    edges = np.sort(np.concatenate((faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]])), axis=1)
    unique, counts = np.unique(edges, axis=0, return_counts=True)
    interior_boundaries = []
    for edge in unique[counts == 1]:
        start, end = surface.mesh.vertices[edge, :2]
        delta = end-start
        lo, hi = 0., 1.
        for axis in range(2):
            if abs(delta[axis]) < 1e-12:
                if abs(start[axis]) >= half_width-1e-7:
                    hi = -1.
            else:
                limits = sorted(((-half_width+1e-7-start[axis])/delta[axis],
                                 (half_width-1e-7-start[axis])/delta[axis]))
                lo, hi = max(lo, limits[0]), min(hi, limits[1])
        if hi-lo > 1e-7:
            interior_boundaries.append(edge.tolist())
    # 无正面积重叠时，裁剪面积之和等于域面积才可认为连续区域无正面积缺口。
    accepted = (not overlaps and not occlusions and not interior_boundaries and
                np.all(counts <= 2) and abs(covered-4*half_width**2) <= 1e-6)
    return dict(half_width_mm=half_width, height_window_mm=[-2, 3], min_normal_z=.5,
                faces=len(polygons), area_sum_mm2=covered, domain_area_mm2=4*half_width**2,
                overlap_pairs=overlaps, occlusion_pairs=occlusions,
                interior_boundary_edges=interior_boundaries, accepted=bool(accepted)), polygons


def overlay_error(surface, vertices, faces):
    """每个输出面与原面叠置；分片线性高度差的绝对最大值出现在交叠多边形顶点。"""
    errors = np.zeros(len(faces))
    coverage_error = np.zeros(len(faces))
    for k, triangle in enumerate(vertices[faces]):
        polygon = triangle[:, :2]
        area = 0.
        bbox = (*polygon.min(axis=0), *polygon.max(axis=0))
        for i in surface.tree.intersection(bbox):
            original = surface.triangles[i]
            if original[:, 2].min() < -2 or original[:, 2].max() > 3 or surface.mesh.face_normals[i, 2] < .5:
                continue
            intersection = clip_polygon(polygon, original[:, :2])
            intersection_area = polygon_area(intersection)
            if intersection_area <= 1e-12:
                continue
            area += intersection_area
            delta = np.abs(triangle_height(original, intersection)-triangle_height(triangle, intersection))
            errors[k] = max(errors[k], float(delta.max()))
        coverage_error[k] = abs(area-polygon_area(polygon))
    return errors, coverage_error
