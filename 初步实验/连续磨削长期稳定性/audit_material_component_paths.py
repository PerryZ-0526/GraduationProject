"""对小闭壳核查连续材料直线路径；不删面、不改提取算法。"""
import argparse
from fractions import Fraction
import json
from pathlib import Path
import sys
import numpy as np
import pyvista as pv
import trimesh


def rational_point(point):
    return tuple(Fraction(float(x)) for x in point)


def subtract(a, b):
    return tuple(x - y for x, y in zip(a, b))


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def clip(value):
    return min(Fraction(1), max(Fraction(0), value))


def segment_distance_squared(p0, p1, q0, q1):
    u, v, w = subtract(p1, p0), subtract(q1, q0), subtract(p0, q0)
    a, b, c, d, e = dot(u, u), dot(u, v), dot(v, v), dot(u, w), dot(v, w)
    # 凸二次距离的最小值只需检查内部驻点和四条边界的最小值。
    candidates = [(Fraction(0), clip(e / c) if c else Fraction(0)),
                  (Fraction(1), clip((e + b) / c) if c else Fraction(0)),
                  (clip(-d / a) if a else Fraction(0), Fraction(0)),
                  (clip((b - d) / a) if a else Fraction(0), Fraction(1))]
    determinant = a * c - b * b
    if determinant > 0:
        s, t = (b * e - c * d) / determinant, (a * e - b * d) / determinant
        if 0 <= s <= 1 and 0 <= t <= 1:
            candidates.append((s, t))
    return min(dot(tuple(wi + s * ui - t * vi for wi, ui, vi in zip(w, u, v)),
                   tuple(wi + s * ui - t * vi for wi, ui, vi in zip(w, u, v))) for s, t in candidates)


def box_path_margin(p, q, rotation, shift, body):
    r = [[Fraction(float(x)) for x in row] for row in rotation]
    h = rational_point(shift)
    local = [tuple(sum((point[i] - h[i]) * r[i][j] for i in range(3)) for j in range(3)) for point in (p, q)]
    boxes = [([0, 0, 0], [2.2, 1.8, .18])] if body == 'thin_wall' else [([-1.02, 0, 0], [.9, 1.8, .8]), ([1.02, 0, 0], [.9, 1.8, .8])]
    # 同一凸盒内两个端点都严格在内部，整条线段便在该初始材料盒内部。
    return max(min(Fraction(float(half[j])) - abs(x[j] - Fraction(float(center[j]))) for x in local for j in range(3))
               for center, half in boxes)


def winding(point, vertices, faces):
    vectors = vertices[faces] - point
    lengths = np.linalg.norm(vectors, axis=2)
    a, b, c = vectors[:, 0], vectors[:, 1], vectors[:, 2]
    numerator = np.einsum('ij,ij->i', a, np.cross(b, c))
    denominator = (lengths.prod(axis=1) + np.einsum('ij,ij->i', a, b) * lengths[:, 2]
                   + np.einsum('ij,ij->i', b, c) * lengths[:, 0] + np.einsum('ij,ij->i', c, a) * lengths[:, 1])
    return float(np.sum(2 * np.arctan2(numerator, denominator)) / (4 * np.pi))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(args.input / '评价启动前冻结方法'))
    from timed_paths import beijing_now, digest
    from material_state import initial_field, capsule_field
    # 六项解析距离控制包含平行、交叉、端点、零长度和内部最近点。
    controls = [(((0, 0, 0), (1, 0, 0), (0, 1, 0), (1, 1, 0)), Fraction(1)),
                (((-1, 0, 0), (1, 0, 0), (0, -1, 0), (0, 1, 0)), Fraction(0)),
                (((0, 0, 0), (1, 0, 0), (2, 0, 0), (3, 0, 0)), Fraction(1)),
                (((0, 0, 0), (0, 0, 0), (0, 2, 0), (0, 2, 0)), Fraction(4)),
                (((-1, 0, 0), (1, 0, 0), (0, -1, 2), (0, 1, 2)), Fraction(4)),
                (((0, 0, 0), (0, 0, 0), (-1, 1, 0), (1, 1, 0)), Fraction(1))]
    results = [segment_distance_squared(*(rational_point(p) for p in points)) == expected for points, expected in controls]
    if not all(results):
        raise ValueError('有限解析距离控制失败')
    radius_squared = Fraction(.4) ** 2
    rows = []
    for folder in sorted(args.input.glob('路线[0-9][0-9]')):
        plan = json.loads((folder / '01-实际执行输入与方法绑定.json').read_text(encoding='utf-8'))
        record = json.loads((folder / '03-实际四方法完整记录.json').read_text(encoding='utf-8'))
        asset = np.load(plan['asset'])
        xs = [-2.1, 0, 2.1] if plan['body'] == 'thin_wall' else [-1.82, -1.02, -.22, .22, 1.02, 1.82]
        zs = [-.15, 0, .15] if plan['body'] == 'thin_wall' else [-.7, 0, .7]
        local_anchors = np.array([(x, y, z) for x in xs for y in (-1.7, 0, 1.7) for z in zs])
        anchors = local_anchors @ np.linalg.inv(asset['rotation']) + asset['shift_mm']
        for attempt in record['attempts']:
            if not attempt['method'].startswith('odc'):
                continue
            poly = pv.read(attempt['file'])
            vertices, faces = np.asarray(poly.points), poly.faces.reshape(-1, 4)[:, 1:]
            mesh = trimesh.Trimesh(vertices, faces, process=False)
            components = trimesh.graph.connected_components(mesh.face_adjacency, nodes=np.arange(len(faces)))
            large = [c for c in components if len(c) > 100]
            knots = asset['knots_mm'][asset['knot_times_s'] <= asset['times_s'][attempt['material_version']]]
            segments = [(rational_point(a), rational_point(b)) for a, b in zip(knots[:-1], knots[1:])]
            for component in components:
                if len(component) > 100:
                    continue
                center = vertices[np.unique(faces[component])].mean(axis=0)
                start = rational_point(center)
                witnesses = []
                for anchor in anchors:
                    end = rational_point(anchor)
                    margin = box_path_margin(start, end, asset['rotation'], asset['shift_mm'], plan['body'])
                    if margin <= 0:
                        continue
                    # 浮点采样仅预筛候选，接受证据始终重新检查整条线段的有理最小距离。
                    sampled = center + np.linspace(0, 1, 33)[:, None] * (anchor - center)
                    if any(np.min(capsule_field(sampled, a, b, .4)) <= 0 for a, b in zip(knots[:-1], knots[1:])):
                        continue
                    distances = [segment_distance_squared(start, end, a, b) for a, b in segments]
                    minimum = min(distances)
                    if minimum <= radius_squared:
                        continue
                    target_winding = [winding(anchor, vertices, faces[c]) for c in large]
                    if not any(abs(x) > .99 for x in target_winding):
                        continue
                    witnesses.append({'anchor_mm': anchor.tolist(), 'initial_box_margin': float(margin),
                                      'minimum_capsule_squared_clearance': str(minimum - radius_squared),
                                      'large_component_winding_fp64': target_winding})
                    break
                value = initial_field(((center - asset['shift_mm']) @ asset['rotation'])[None], plan['body'])
                for a, b in zip(knots[:-1], knots[1:]):
                    value = np.maximum(value, -capsule_field(center[None], a, b, .4))
                rows.append({'route': folder.name, 'method': attempt['method'], 'event': attempt['material_version'],
                             'file': attempt['file'], 'sha256': digest(attempt['file']), 'faces': len(component),
                             'area_mm2': float(mesh.area_faces[component].sum()), 'center_mm': center.tolist(),
                             'center_material_field': float(value[0]), 'small_component_winding_fp64': winding(center, vertices, faces[component]),
                             'material_path_witnesses': witnesses})
        print(json.dumps({'route': folder.name, 'small_components': sum(x['route'] == folder.name for x in rows)}, ensure_ascii=False), flush=True)
    result = {'updated_at_beijing': beijing_now(), 'source_sha256': digest(__file__), 'distance_controls': results, 'rows': rows,
              'scope': '二进制64材料参数的连续线段有理距离及凸盒证据；壳内外使用FP64绕数，未证明全部材料连通性或网格精确嵌入'}
    with (args.output / '01-小闭壳材料路径核查.json').open('x', encoding='utf-8') as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)


if __name__ == '__main__':
    main()
