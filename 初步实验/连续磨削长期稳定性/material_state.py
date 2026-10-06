"""解析材料与球钻扫掠的窄带格点状态；组合场不称为精确欧氏SDF。"""
import numpy as np


def box_field(points, center, half):
    delta = np.abs(points - center) - half
    return np.linalg.norm(np.maximum(delta, 0), axis=-1) + np.minimum(np.max(delta, axis=-1), 0)


def initial_field(points, body):
    if body == 'sphere':
        return np.linalg.norm(points, axis=-1) - 1.7
    if body == 'gap':
        left = box_field(points, np.array([-1.02, 0, 0]), np.array([0.9, 1.8, 0.8]))
        right = box_field(points, np.array([1.02, 0, 0]), np.array([0.9, 1.8, 0.8]))
        return np.minimum(left, right)
    half = np.array([2.2, 1.8, 0.18 if body == 'thin_wall' else 0.75])
    if body not in ('thin_wall', 'slab'):
        raise ValueError('不支持的解析材料')
    return box_field(points, np.zeros(3), half)


def capsule_field(points, start, end, radius):
    edge = end - start
    squared = float(edge @ edge)
    # 停留事件仍是球体扫掠，不能因零位移而遗漏材料。
    parameter = np.zeros(points.shape[:-1]) if squared == 0 else np.clip(
        np.sum((points - start) * edge, axis=-1) / squared, 0, 1)
    closest = start + parameter[..., None] * edge
    return np.linalg.norm(points - closest, axis=-1) - radius


class MaterialState:
    def __init__(self, body, spacing):
        if not np.isfinite(spacing) or spacing <= 0:
            raise ValueError('格点间距必须有限且为正')
        count = int(round(7.2 / spacing))
        if not np.isclose(count * spacing, 7.2, rtol=0, atol=1e-12):
            raise ValueError('当前固定实验域要求间距整除7.2毫米')
        self.axis = np.linspace(-3.6, 3.6, count + 1)
        self.spacing = spacing
        self.band = 2 * spacing
        self.body = body
        self.points = np.stack(np.meshgrid(self.axis, self.axis, self.axis, indexing='ij'), axis=-1)
        self.initial = np.clip(initial_field(self.points, body), -self.band, self.band)
        self.field = self.initial.copy()

    def apply(self, start, end, radius):
        start, end = np.asarray(start, dtype=np.float64), np.asarray(end, dtype=np.float64)
        if start.shape != (3,) or end.shape != (3,) or not np.all(np.isfinite([start, end])):
            raise ValueError('扫掠端点必须为有限三维坐标')
        if not np.isfinite(radius) or radius <= 0:
            raise ValueError('球钻半径必须有限且为正')
        lower = np.minimum(start, end) - radius - self.band
        upper = np.maximum(start, end) + radius + self.band
        if np.any(lower < self.axis[0]) or np.any(upper > self.axis[-1]):
            raise ValueError('扫掠及窄带越过固定实验域，禁止静默裁剪')
        slices = tuple(slice(np.searchsorted(self.axis, lo, side='left'),
                             np.searchsorted(self.axis, hi, side='right')) for lo, hi in zip(lower, upper))
        current = self.field[slices]
        cut = capsule_field(self.points[slices], start, end, radius)
        updated = np.maximum(current, np.clip(-cut, -self.band, self.band))
        # 半径加窄带之外，负工具场不大于窄带下界，故局部更新与全域更新一致。
        changed = int(np.count_nonzero(updated != current))
        removed = int(np.count_nonzero((current < 0) & (updated >= 0)))
        current[:] = updated
        return {'touched_nodes': int(current.size), 'changed_nodes': changed,
                'removed_negative_nodes': removed}

    def rebuild(self, starts, ends, radius):
        # 原初态加完整事件前缀的全域重建只用于同算法一致性核对。
        field = self.initial.copy()
        for start, end in zip(starts, ends):
            field = np.maximum(field, np.clip(-capsule_field(self.points, start, end, radius),
                                             -self.band, self.band))
        return field
