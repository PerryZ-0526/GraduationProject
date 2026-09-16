"""已通过投影检查的真实骨面高度查询和隔离的局部浅磨削实验。"""
from pathlib import Path
import sys
import numpy as np
import matplotlib.tri as mtri
from surface_patch import triangle_height, overlay_error

sys.path.insert(0, str(Path(__file__).parents[1]/'局部区域重建阶段一'))
from patch_model import PatchModel, Sweep, Rejected, distance2, mesh_quality


class BoneChart:
    """原始CT三角面上的分片线性查询，不把拟合或平滑当作原始几何。"""
    def __init__(self, surface, polygons):
        self.surface = surface
        self.ids = np.array(list(polygons))
        points = np.concatenate(list(polygons.values()))
        self.lower, self.upper = points.min(axis=0), points.max(axis=0)
        mesh = surface.mesh
        triangles = mesh.triangles[self.ids]
        triangulation = mtri.Triangulation(mesh.vertices[:, 0], mesh.vertices[:, 1], mesh.faces[self.ids])
        self.finder = triangulation.get_trifinder()
        self.gradient = np.linalg.solve(triangles[:, 1:, :2]-triangles[:, :1, :2],
                                        (triangles[:, 1:, 2]-triangles[:, :1, 2])[..., None])[..., 0]
        self.intercept = triangles[:, 0, 2]-np.sum(self.gradient*triangles[:, 0, :2], axis=1)
        self.lipschitz = float(np.linalg.norm(self.gradient, axis=1).max())
        self.ceiling = max(float(triangle_height(mesh.triangles[i], polygon).max())
                           for i, polygon in polygons.items())

    def height(self, xy):
        if np.any(xy < self.lower-1e-10) or np.any(xy > self.upper+1e-10):
            raise Rejected('查询越过已裁剪验证区域，不能外推原始三角面')
        ids = self.finder(xy[..., 0], xy[..., 1])
        if np.any(ids < 0):
            raise Rejected('查询超出已验证原始骨面图域')
        return np.sum(self.gradient[ids]*xy, axis=-1)+self.intercept[ids]


class RealPatch(PatchModel):
    """只导出开放局部表面，不冒充已拼接的整骨或完整手术计划。"""
    def __init__(self, chart, spacing=.25, half_width=4.):
        self.chart = None
        super().__init__(spacing, 'plane', samples=32, half_width=half_width)
        self.chart = chart
        self.vertices[:, 2] = chart.height(self.xy)
        self.ceiling, self.base_lipschitz = chart.ceiling, chart.lipschitz
        self.q, self.angles, _ = mesh_quality(self.vertices, self.faces)
        self.bounds, coverage = overlay_error(chart.surface, self.vertices, self.faces)
        if coverage.max() > 1e-7 or self.q.min() < .4 or self.angles.min() < 25 or self.bounds.max() > .1:
            raise Rejected('真实骨面初始重建未通过验收')

    def height(self, xy, tools):
        if self.chart is None:
            return super().height(xy, tools)
        result = self.chart.height(xy)
        for tool in tools:
            squared = distance2(xy, tool)
            inside = squared <= tool.radius**2
            lower = tool.z-np.sqrt(np.maximum(0., tool.radius**2-squared))
            result = np.where(inside, np.minimum(result, lower), result)
        return result


def local_trajectory(center_z=2.95):
    """新建局部交叉轨迹；默认沿用面精高度，降低球心仅用于非临床深度压力测试。"""
    coordinates = np.linspace(-1, 1, 9)
    return ([Sweep((a, .037), (b, .037), 3., center_z) for a, b in zip(coordinates[:-1], coordinates[1:])]+
            [Sweep((.037, a), (.037, b), 3., center_z) for a, b in zip(coordinates[:-1], coordinates[1:])])
