"""闭合非凸工具的表面距离邻域，不用凸包填充工具间隙。"""
import numpy as np


def triangle_squared_distances(points, triangle):
    """用FP64平面侧测试与闭线段距离，不使用细长面的Gram矩阵逆。"""
    a, b, c = triangle
    normal = np.cross(b-a, c-a)
    area = np.dot(normal, normal)
    if not np.isfinite(area) or area <= 0:
        raise ValueError("工具三角面退化或面积计算非有限")
    height = (points-a) @ normal
    projection = points-height[:, None]*normal/area
    inside = np.ones(len(points), bool)
    for start, end in ((a, b), (b, c), (c, a)):
        inside &= np.cross(end-start, projection-start) @ normal >= 0
    distance = np.full(len(points), np.inf)
    for start, end in ((a, b), (b, c), (c, a)):
        edge = end-start
        parameter = np.clip((points-start) @ edge/np.dot(edge, edge), 0, 1)
        difference = points-(start+parameter[:, None]*edge)
        distance = np.minimum(distance, np.einsum("ij,ij->i", difference, difference))
    distance[inside] = height[inside]**2/area
    if not np.isfinite(distance).all():
        raise ValueError("工具距离查询非有限")
    return distance


def surface_band(points, tool, margin=.1):
    """AABB只过滤候选，最终仍按三角表面距离决定自由点范围。"""
    points = np.asarray(points, dtype=np.float64)
    if points.ndim != 2 or points.shape[1] != 3 or not np.isfinite(points).all():
        raise ValueError("工具邻域点无效")
    if not np.isfinite(margin) or margin < 0:
        raise ValueError("工具表面邻域余量无效")
    if not tool.is_watertight or not tool.is_winding_consistent or not np.isfinite(tool.vertices).all():
        raise ValueError("工具不闭合、绕序不一致或非有限")
    if np.any(tool.area_faces <= 0):
        raise ValueError("工具包含退化三角面")
    near = np.zeros(len(points), bool)
    for triangle in tool.triangles:
        # 不把非凸工具的全局包围盒当活动域；过滤后检查实际面距离。
        selected = np.flatnonzero(~near & np.all(points >= triangle.min(axis=0)-margin, axis=1)
                                  & np.all(points <= triangle.max(axis=0)+margin, axis=1))
        if len(selected):
            near[selected] = triangle_squared_distances(points[selected], triangle) <= margin**2
    return near
