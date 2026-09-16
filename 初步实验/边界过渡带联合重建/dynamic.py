"""通过初始联合验收后，沿同一共边网格执行局部逐步更新和整骨复核。"""
from time import perf_counter
import numpy as np
from joint import mesh_quality, Rejected
from stitch import edges_of, topology, audit_candidate, self_intersection_flags
from real_patch import RealPatch, local_trajectory
from surface_patch import overlay_error
from intersections import resolve_flags


class JointPatch(RealPatch):
    """沿用已验证的扫掠与误差证书，不再重新生成开放规则方形底网。"""
    def __init__(self, chart, candidate):
        self.chart, self.kind, self.samples = chart, 'real', 32
        self.vertices, self.faces = candidate['vertices'].copy(), candidate['faces'].copy()
        self.xy = self.vertices[:, :2].copy()
        self.ceiling, self.base_lipschitz = chart.ceiling, chart.lipschitz
        edges, counts = edges_of(self.faces)
        self.boundary_edges = edges[counts == 1]
        self.boundary = np.unique(self.boundary_edges)
        tri = self.xy[self.faces]
        self.face_centers = tri.mean(axis=1)
        self.diameters = np.linalg.norm(tri-np.roll(tri, 1, axis=1), axis=2).max(axis=1)
        self.tools, self.attempts = [], []
        self.q, self.angles, _ = mesh_quality(self.vertices, self.faces)
        self.bounds, coverage = overlay_error(chart.surface, self.vertices, self.faces)
        self.coverage_max = float(coverage.max())

    def height(self, xy, tools):
        started = perf_counter()
        try:
            return super().height(xy, tools)
        finally:
            self.height_ms = getattr(self, 'height_ms', 0.)+(perf_counter()-started)*1000

    def update(self, tool):
        self.height_ms = self.certificate_ms = 0.
        try:
            return super().update(tool)
        finally:
            # 高度查询包含在证书计算中，两个包含式计时不能相加当总耗时。
            self.attempts[-1].update(height_ms=self.height_ms, certificate_ms=self.certificate_ms)

    def certify(self, vertices, indices, tools, lipschitz):
        """对粗过渡面自适应加密验证格点，不移动网格，不放宽几何误差门槛。"""
        started = perf_counter()
        saved = self.samples
        bounds = np.full(len(indices), np.inf)
        pending = np.arange(len(indices))
        sampled_max, queries = 0., 0
        try:
            for n in (32, 64, 128, 256, 512):
                self.samples = n
                values, sampled, count = super().certify(vertices, indices[pending], tools, lipschitz)
                bounds[pending] = values
                sampled_max, queries = max(sampled_max, sampled), queries+count
                pending = np.flatnonzero(bounds > .1)
                if not len(pending):
                    break
        finally:
            self.samples = saved
            self.certificate_ms = getattr(self, 'certificate_ms', 0.)+(perf_counter()-started)*1000
        return bounds+self.base_lipschitz*1e-10, sampled_max, queries


def iter_sequence(candidate, chart, z=2.95, model_factory=JointPatch, trajectory=None):
    """逐次返回完成整骨验收的状态；批量实验和交互窗口共享同一门控。"""
    precheck, _, _ = audit_candidate(chart.surface, candidate)
    resolve_flags(candidate, precheck)
    if not precheck['accepted']:
        raise Rejected('初始整骨候选未通过联合验收，禁止开始磨削')
    model = model_factory(chart, candidate)
    initial = model.vertices.copy()
    model.snapshots = [initial]
    yield model, None
    # 默认轨迹不变；显式实验轨迹仍经过相同的逐状态与整骨验收。
    for tool in local_trajectory(z) if trajectory is None else trajectory:
        started = perf_counter()
        old = (model.vertices, model.tools, model.bounds, model.q, model.angles)
        try:
            row = model.update(tool).copy()
        except Rejected:
            row = model.attempts[-1].copy()
            row['total_ms'] = (perf_counter()-started)*1000
            yield model, row
            break
        whole = candidate['whole'].copy()
        whole.vertices[candidate['mapping']] = model.vertices
        proposed = dict(candidate, whole=whole)
        proposed['intersection_flags'] = self_intersection_flags(whole.vertices, whole.faces)
        check = dict(topology(whole), degenerate=row['degenerate'], bad_faces=0,
                     error_max_mm=row['error_bound_mm'], coverage_max_mm2=model.coverage_max,
                     coverage_reused_fixed_xy=True)
        resolve_flags(proposed, check)
        row.update(check, self_intersection_flags=int(proposed['intersection_flags'].sum()),
                   total_ms=(perf_counter()-started)*1000,
                   boundary_unchanged=bool(np.array_equal(model.vertices[model.boundary], initial[model.boundary])))
        row['accepted'] &= row['boundary_unchanged']
        if not row['accepted']:
            model.vertices, model.tools, model.bounds, model.q, model.angles = old
            row['reason'] = '整骨复核失败，回滚几何、历史、误差与质量状态'
        else:
            model.snapshots.append(model.vertices.copy())
        model.attempts[-1] = row.copy()
        print('step', row['step'], row['accepted'], row.get('min_angle_deg'), row.get('error_bound_mm'), flush=True)
        yield model, row
        if not row['accepted']:
            break


def run_sequence(candidate, chart, z=2.95, model_factory=JointPatch, trajectory=None):
    """批量消费同一逐状态生成器，保持原返回结构与实验默认参数。"""
    records = []
    for model, row in iter_sequence(candidate, chart, z, model_factory, trajectory):
        if row is not None:
            records.append(row)
    return model, records
