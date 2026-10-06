"""新姿态输入与材料查询适配，提取算法和预算不据评价输出改动。"""
import json
from pathlib import Path
import numpy as np
from scipy.interpolate import RegularGridInterpolator
from material_state import MaterialState, initial_field, capsule_field
from timed_paths import make_path, beijing_now, digest
from audit_feature_probes import tool_clearance, crossings


def probe_positions(body):
    return ([(x, y) for x in (-1.95, 1.95) for y in (-1.65, 1.65)] if body == 'thin_wall' else
            [(y, z) for y in (-1.75, 1.75) for z in (-.75, .75)] + [(y, z) for y in (-1.5, 1.5) for z in (0, .3)])


def generate_inputs(folder):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=False)
    seed = 2026100608
    rng = np.random.default_rng(seed)
    assets = []
    for index in range(8):
        body = 'thin_wall' if index % 2 == 0 else 'gap'
        q = rng.normal(size=4)
        w, x, y, z = q / np.linalg.norm(q)
        rotation = np.array([[1 - 2 * (y*y + z*z), 2 * (x*y - z*w), 2 * (x*z + y*w)],
                             [2 * (x*y + z*w), 1 - 2 * (x*x + z*z), 2 * (y*z - x*w)],
                             [2 * (x*z - y*w), 2 * (y*z + x*w), 1 - 2 * (x*x + y*y)]])
        shift = rng.uniform(-.12, .12, size=3)
        times, _, knot_times, local_knots = make_path(10)
        local_knots = local_knots.copy()
        local_knots[1:5, :2] += rng.uniform(-.08, .08, size=(4, 2))
        local_knots[5:7, 0] += rng.uniform(-.08, .08, size=2)
        local_knots[5:7, 1] += rng.uniform(-.04, .04, size=2)
        local_knots[7] = local_knots[6]
        direction = 2 if body == 'thin_wall' else 0
        clearance = min(tool_clearance(direction, p, local_knots) for p in probe_positions(body))
        knots = local_knots @ rotation.T + shift
        centers = np.column_stack([np.interp(times, knot_times, knots[:, i]) for i in range(3)])
        # 世界坐标分段线性运动是本批真实输入定义，不假设变换与插值逐位交换。
        if np.any(np.minimum(knots[:-1], knots[1:]) - .4 - .12 < -3.6) or np.any(np.maximum(knots[:-1], knots[1:]) + .4 + .12 > 3.6):
            raise ValueError('扫掠和窄带越过固定实验域')
        file = folder / f'路线{index:02d}_{body}.npz'
        np.savez(file, times_s=times, centers_mm=centers, knot_times_s=knot_times, knots_mm=knots,
                 local_knots_mm=local_knots, rotation=rotation, shift_mm=shift)
        assets.append({'route_id': index, 'body': body, 'file': str(file), 'sha256': digest(file),
                       'events': 1000, 'tool_clearance_lower_bound_mm': clearance,
                       'all_probe_rays_uncut': bool(clearance > 0),
                       'rotation_orthogonality_residual': float(np.max(np.abs(rotation.T @ rotation - np.eye(3))))})
    manifest = {'created_at_beijing': beijing_now(), 'seed': seed, 'assets': assets,
                'scope': '方法冻结后生成的8条新姿态/平移/轨迹评价，2个已见形状家族；不是新患者或新钻型'}
    (folder / '01-新输入资产清单.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    return manifest


class PoseMaterial(MaterialState):
    def __init__(self, body, rotation, shift):
        super().__init__(body, .06)
        self.rotation, self.shift = rotation, shift
        # 仅改变输入的初态姿态，胶囊世界坐标更新沿用已冻结材料机制。
        self.initial = np.clip(initial_field((self.points - shift) @ rotation, body), -self.band, self.band)
        self.field = self.initial.copy()


def extract_pose(torch, extractor, state, knots, source):
    interpolator = RegularGridInterpolator((state.axis,) * 3, state.field, bounds_error=True)
    counts = {'calls': 0, 'points': 0}

    def query(points):
        array = points.detach().cpu().numpy()
        if source == 'grid':
            value = interpolator(array)
        else:
            value = initial_field((array - state.shift) @ state.rotation, state.body)
            for a, b in zip(knots[:-1], knots[1:]):
                value = np.maximum(value, -capsule_field(array, a, b, .4))
            value = np.clip(value, -state.band, state.band)
        counts['calls'] += 1
        counts['points'] += len(array)
        return torch.from_numpy(np.asarray(value, dtype=np.float64))

    vertices, faces = extractor.extract_mesh(query, min_coord=[-3.6] * 3, max_coord=[3.6] * 3,
                                             num_grid=len(state.axis) - 1, batch_size=1000000)
    return vertices.cpu().numpy(), faces.cpu().numpy().reshape(-1, 3), counts


def quadratic_interval(a, b, c):
    if a == 0:
        return (-np.inf, np.inf) if c <= 0 else None
    discriminant = b*b - 4*a*c
    if discriminant < 0:
        return None
    root = np.sqrt(discriminant)
    q = -.5 * (b + np.copysign(root, b))
    values = (-b / (2*a),) * 2 if q == 0 else (q / a, c / q)
    return min(values), max(values)


def capsule_interval(origin, direction, start, end):
    intervals = []
    for center in (start, end):
        delta = origin - center
        interval = quadratic_interval(float(direction @ direction), float(2 * (direction @ delta)), float(delta @ delta - .4**2))
        if interval is not None:
            intervals.append(interval)
    edge = end - start
    square = float(edge @ edge)
    if square > 0:
        cross_direction = np.cross(direction, edge)
        cross_origin = np.cross(origin - start, edge)
        cylinder = quadratic_interval(float(cross_direction @ cross_direction / square),
                                      float(2 * (cross_direction @ cross_origin) / square),
                                      float(cross_origin @ cross_origin / square - .4**2))
        slope, offset = float(edge @ direction / square), float(edge @ (origin - start) / square)
        axial = ((-np.inf, np.inf) if 0 <= offset <= 1 else None) if slope == 0 else tuple(sorted((-offset / slope, (1 - offset) / slope)))
        if cylinder is not None and axial is not None:
            lo, hi = max(cylinder[0], axial[0]), min(cylinder[1], axial[1])
            if lo <= hi:
                intervals.append((lo, hi))
    # 球端加有限圆柱就是胶囊，凸集合与射线的交集是单一区间。
    return None if not intervals else (min(x[0] for x in intervals), max(x[1] for x in intervals))


def expected_crossings(state, position, knots):
    axis = 2 if state.body == 'thin_wall' else 0
    local_origin = np.zeros(3)
    local_origin[[i for i in range(3) if i != axis]] = position
    inverse = np.linalg.inv(state.rotation)
    origin, direction = local_origin @ inverse + state.shift, inverse[axis]
    remaining = [(-.18, .18)] if state.body == 'thin_wall' else [(-1.92, -.12), (.12, 1.92)]
    # 对每个真实胶囊区间作集合差，受切削的旧探针不再与原初态尺寸比较。
    for start, end in zip(knots[:-1], knots[1:]):
        cut = capsule_interval(origin, direction, start, end)
        if cut is None or cut[1] <= cut[0]:
            continue
        updated = []
        for lo, hi in remaining:
            if cut[1] <= lo or cut[0] >= hi:
                updated.append((lo, hi))
            else:
                if cut[0] > lo:
                    updated.append((lo, min(hi, cut[0])))
                if cut[1] < hi:
                    updated.append((max(lo, cut[1]), hi))
        remaining = updated
    return [float(x) for pair in remaining for x in pair]


def feature_review(poly, state, knots):
    local = poly.copy()
    local.points = (np.asarray(poly.points, dtype=np.float64) - state.shift) @ state.rotation
    direction = 2 if state.body == 'thin_wall' else 0
    result = []
    for position in probe_positions(state.body):
        expected = expected_crossings(state, position, knots)
        item = crossings(local, direction, position)
        values = item['crossings_mm']
        error = None if len(values) != len(expected) else float(np.max(np.abs(np.asarray(values) - expected)))
        result.append(dict(item, fixed_local_coordinates_mm=position, analytic_expected_mm=expected,
                           error_max_mm=error, reference_scope='FP64解析胶囊区间集合差，不是精确算术证书'))
    return result
