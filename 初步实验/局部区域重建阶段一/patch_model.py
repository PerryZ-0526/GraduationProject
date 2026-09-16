"""无倒扣高度图的规则三角局部重建；单位毫米，仅用于阶段一机制验证。"""
from dataclasses import dataclass
from time import perf_counter
import numpy as np


@dataclass(frozen=True)
class Sweep:
    """球心等高的水平线段扫掠；不支持倾斜轨迹和任意姿态切削。"""
    start: tuple
    end: tuple
    radius: float
    z: float


class Rejected(RuntimeError):
    """候选违反适用范围、单元质量或几何误差门槛。"""


def distance2(xy, tool):
    """到水平扫掠线段的平方距离，零长度线段对应球磨钻驻点。"""
    start, end = np.asarray(tool.start), np.asarray(tool.end)
    delta = end-start
    length2 = delta @ delta
    t = np.zeros(xy.shape[:-1]) if length2 == 0 else np.clip((xy-start) @ delta/length2, 0., 1.)
    return np.sum((xy-start-t[..., None]*delta)**2, axis=-1)


def base_height(xy, kind):
    if kind == 'plane':
        return np.zeros(xy.shape[:-1])
    if kind == 'bowl':
        return 7.5-np.sqrt(100.-np.sum(xy**2, axis=-1))
    raise ValueError('未知解析面')


def height(xy, kind, tools):
    """从解析面及扫掠历史求下包络，不从已三角化表面累积高度误差。"""
    result = base_height(xy, kind)
    for tool in tools:
        squared = distance2(xy, tool)
        inside = squared <= tool.radius**2
        lower = tool.z-np.sqrt(np.maximum(0., tool.radius**2-squared))
        result = np.where(inside, np.minimum(result, lower), result)
    return result


def mesh_quality(vertices, faces):
    """逐面计算形状与最小角，不用差面百分比替代逐面门槛。"""
    triangles = vertices[faces]
    edges = np.roll(triangles, -1, axis=1)-triangles
    squared = np.sum(edges**2, axis=2)
    cross = np.cross(edges[:, 0], -edges[:, 2])
    area2 = np.linalg.norm(cross, axis=1)
    q = 2*np.sqrt(3)*area2/squared.sum(axis=1)
    cosines = -np.sum(edges*np.roll(edges, 1, axis=1), axis=2)/np.sqrt(squared*np.roll(squared, 1, axis=1))
    angle = np.degrees(np.arccos(np.clip(cosines, -1, 1))).min(axis=1)
    return q, angle, area2


def lattice(spacing, half_width=4.):
    """按给定区域半宽构造共享索引底网；默认保留阶段一的8 mm区域。"""
    nx, ny = int(np.ceil(2*half_width/spacing)), int(np.ceil(2*half_width/(spacing*np.sqrt(3)/2)))
    xy = np.array([(-half_width+i*spacing+(j % 2)*spacing/2, -half_width+j*spacing*np.sqrt(3)/2)
                   for j in range(ny+1) for i in range(nx+1)])
    faces = []
    for j in range(ny):
        for i in range(nx):
            a = j*(nx+1)+i
            b, c, d = a+1, a+nx+1, a+nx+2
            faces.extend([(a, b, c), (b, d, c)] if j % 2 == 0 else [(a, b, d), (a, d, c)])
    return xy, np.asarray(faces)


class PatchModel:
    """固定底网连接、局部重采样高度；并非任意曲面空腔重三角化算法。"""
    def height(self, xy, tools):
        """几何查询入口；解析实验默认不变，真实局部面可提供独立原面查询。"""
        return height(xy, self.kind, tools)

    def __init__(self, spacing=.2, kind='plane', samples=32, half_width=4.):
        self.xy, self.faces = lattice(spacing, half_width)
        self.kind, self.samples = kind, samples
        self.vertices = np.column_stack((self.xy, base_height(self.xy, kind)))
        self.ceiling = float(self.vertices[:, 2].max())
        self.base_lipschitz = (0. if kind == 'plane' else
                              float(np.sqrt(np.sum(self.xy**2, axis=1).max())/
                                    np.sqrt(100.-np.sum(self.xy**2, axis=1).max())))
        edges = np.sort(np.concatenate([self.faces[:, [0, 1]], self.faces[:, [1, 2]],
                                        self.faces[:, [2, 0]]]), axis=1)
        unique, counts = np.unique(edges, axis=0, return_counts=True)
        self.boundary_edges = unique[counts == 1]
        self.boundary = np.unique(self.boundary_edges)
        assert np.all(counts <= 2)
        assert len(self.xy)-len(unique)+len(self.faces) == 1
        tri_xy = self.xy[self.faces]
        self.face_centers = tri_xy.mean(axis=1)
        self.diameters = np.linalg.norm(tri_xy-np.roll(tri_xy, 1, axis=1), axis=2).max(axis=1)
        self.tools, self.attempts = [], []
        self.q, self.angles, _ = mesh_quality(self.vertices, self.faces)
        self.bounds, _, _ = self.certify(self.vertices, np.arange(len(self.faces)), [], self.base_lipschitz)
        if self.q.min() < .4 or self.angles.min() < 25 or self.bounds.max() > .1:
            raise Rejected('初始区域尚未满足质量与误差门槛')

    def certify(self, vertices, indices, tools, lipschitz):
        """重心格点覆盖证书：抽样误差加(L+三角面梯度)*直径/n，不是仅抽样最大值。"""
        n = self.samples
        barycentric = np.array([(i/n, j/n, 1-(i+j)/n)
                                for i in range(n+1) for j in range(n+1-i)])
        bounds, sampled = [], []
        # 默认保持64面批次；批量消融只改变调用划分，不改变格点或证书公式。
        batch = getattr(self, 'query_batch_faces', 64)
        for begin in range(0, len(indices), batch):
            ids = indices[begin:begin+batch]
            triangles = vertices[self.faces[ids]]
            queries = np.einsum('si,fij->fsj', barycentric, triangles)
            exact = self.height(queries[..., :2], tools)
            errors = np.abs(exact-queries[..., 2])
            matrix = triangles[:, 1:, :2]-triangles[:, :1, :2]
            rhs = triangles[:, 1:, 2]-triangles[:, :1, 2]
            gradient = np.linalg.solve(matrix, rhs[..., None])[..., 0]
            bound = errors.max(axis=1)+(lipschitz+np.linalg.norm(gradient, axis=1))*self.diameters[ids]/n
            bounds.append(bound)
            sampled.append(errors.ravel())
        return np.concatenate(bounds), float(np.max(np.concatenate(sampled))), len(barycentric)*len(indices)

    def update(self, tool):
        started = perf_counter()
        step = len(self.tools)+1
        audit = dict(step=step, accepted=False, tool=tool.__dict__)
        try:
            if tool.radius <= 0 or not np.all(np.isfinite([*tool.start, *tool.end, tool.z, tool.radius])):
                raise Rejected('工具参数不合法')
            gap = tool.z-self.ceiling
            if gap <= 0:
                raise Rejected('球心低于区域最高面：不满足无倒扣高度图适用范围')
            support = np.sqrt(max(0., tool.radius**2-gap**2))
            affected = np.flatnonzero(distance2(self.face_centers, tool) <= (support+self.diameters)**2)
            if gap >= tool.radius:
                affected = np.array([], dtype=int)
            boundary_xy = self.xy[self.boundary_edges]
            if len(affected) and np.any(distance2(boundary_xy.mean(axis=1), tool) <=
                                       (support+np.linalg.norm(np.diff(boundary_xy, axis=1)[:, 0], axis=1)/2)**2):
                raise Rejected('扫掠可能触及固定边界：需要扩展区域，本原型拒绝提交')
            locate_ms = (perf_counter()-started)*1000
            tools = [*self.tools, tool]
            candidate = self.vertices.copy()
            selected = np.unique(self.faces[affected])
            candidate[selected, 2] = self.height(self.xy[selected], tools)
            reconstruct_ms = (perf_counter()-started)*1000-locate_ms
            q, angles, areas = mesh_quality(candidate, self.faces)
            lipschitz = max([self.base_lipschitz]+[
                np.sqrt(max(0., item.radius**2-(item.z-self.ceiling)**2))/(item.z-self.ceiling)
                for item in tools])
            bounds = self.bounds.copy()
            sampled_max, queries = 0., 0
            if len(affected):
                bounds[affected], sampled_max, queries = self.certify(candidate, affected, tools, lipschitz)
            audit.update(min_q=float(q.min()), min_angle_deg=float(angles.min()),
                         degenerate=int(np.sum(areas <= 1e-12)), error_bound_mm=float(bounds.max()),
                         sampled_max_mm=sampled_max, queries=queries, affected_faces=len(affected),
                         faces=len(self.faces), vertices=len(candidate), locate_ms=locate_ms,
                         reconstruct_ms=reconstruct_ms, lipschitz=lipschitz)
            if areas.min() <= 1e-12 or q.min() < .4 or angles.min() < 25 or bounds.max() > .1:
                raise Rejected('逐面质量或垂直几何偏差证书超限')
            # 同一底网是单射且朝向一致的平面三角剖分，提升单值高度不产生表面自相交。
            self.vertices, self.tools, self.bounds = candidate, tools, bounds
            self.q, self.angles = q, angles
            audit['accepted'] = True
            return audit
        except Rejected as exc:
            audit['reason'] = str(exc)
            raise
        finally:
            audit['pipeline_ms'] = (perf_counter()-started)*1000
            self.attempts.append(audit)
