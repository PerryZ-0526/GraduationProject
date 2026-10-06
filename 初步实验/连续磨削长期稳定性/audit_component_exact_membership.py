"""对材料通道两端执行保存二进制64三角面的精确射线奇偶核查。"""
import argparse
from fractions import Fraction
import json
from pathlib import Path
import numpy as np
import pyvista as pv
import trimesh
from audit_material_component_paths import rational_point, subtract, dot
from timed_paths import beijing_now, digest


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def exact_inside(point, vertices, faces):
    origin = rational_point(point)
    for axis in range(3):
        fixed = [i for i in range(3) if i != axis]
        triangle = vertices[faces]
        # 轴向射线的投影包围盒只作原二进制64坐标比较，不使用浮点运算近似边界。
        possible = np.ones(len(faces), dtype=bool)
        for j in fixed:
            possible &= (triangle[:, :, j].min(axis=1) <= point[j]) & (point[j] <= triangle[:, :, j].max(axis=1))
        direction = tuple(Fraction(int(i == axis)) for i in range(3))
        hits, ambiguous = 0, False
        for face in faces[possible]:
            a, b, c = (rational_point(vertices[i]) for i in face)
            e1, e2, offset = subtract(b, a), subtract(c, a), subtract(origin, a)
            p = cross(direction, e2)
            determinant = dot(e1, p)
            if determinant == 0:
                if dot(cross(e1, e2), offset) == 0:
                    ambiguous = True
                    break
                continue
            u = dot(offset, p) / determinant
            q = cross(offset, e1)
            v = dot(direction, q) / determinant
            t = dot(e2, q) / determinant
            if u < 0 or v < 0 or u + v > 1 or t < 0:
                continue
            if t == 0:
                return {'status': 'on_surface', 'inside': None}
            if u == 0 or v == 0 or u + v == 1:
                ambiguous = True
                break
            hits += 1
        if not ambiguous:
            return {'status': 'exact_parity', 'axis': axis, 'positive_hits': hits, 'inside': bool(hits % 2)}
    return {'status': 'ambiguous_all_axes', 'inside': None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, required=True)
    args = parser.parse_args()
    output = args.input / '03-材料路径两端精确网格内外核查.json'
    if output.exists():
        raise ValueError('核查文件禁止覆盖')
    control = pv.Box(bounds=(-1, 1, -1, 1, -1, 1)).triangulate()
    control_faces = control.faces.reshape(-1, 4)[:, 1:]
    controls = [exact_inside(np.array(p), control.points, control_faces) for p in ((.13, .27, .39), (2., .27, .39), (1., .27, .39))]
    if not (controls[0]['inside'] is True and controls[1]['inside'] is False and controls[2]['status'] == 'on_surface'):
        raise ValueError('有限盒体内外和边界控制失败')
    source = args.input / '01-小闭壳材料路径核查.json'
    first = json.loads(source.read_text(encoding='utf-8'))
    rows = []
    cache = {}
    for row in first['rows']:
        file = row['file']
        if file not in cache:
            poly = pv.read(file)
            vertices, faces = np.asarray(poly.points), poly.faces.reshape(-1, 4)[:, 1:]
            mesh = trimesh.Trimesh(vertices, faces, process=False)
            components = trimesh.graph.connected_components(mesh.face_adjacency, nodes=np.arange(len(faces)))
            cache = {file: (vertices, faces, components)}
        vertices, faces, components = cache[file]
        small = [c for c in components if len(c) == row['faces'] and np.array_equal(vertices[np.unique(faces[c])].mean(axis=0), row['center_mm'])]
        if len(small) != 1 or digest(file) != row['sha256']:
            raise ValueError('原核查小闭壳或保存网格摘要不匹配')
        center_inside = exact_inside(np.array(row['center_mm']), vertices, faces[small[0]])
        target = []
        for witness in row['material_path_witnesses']:
            checks = [exact_inside(np.array(witness['anchor_mm']), vertices, faces[c]) for c in components if len(c) > 100]
            target.append({'anchor_mm': witness['anchor_mm'], 'large_components': checks,
                           'inside_any_large': any(x['inside'] is True for x in checks)})
        rows.append({'route': row['route'], 'method': row['method'], 'event': row['event'], 'center_mm': row['center_mm'],
                     'center_small_component': center_inside, 'target_checks': target,
                     'path_connects_small_and_large_interiors': center_inside['inside'] is True and any(x['inside_any_large'] for x in target)})
    result = {'updated_at_beijing': beijing_now(), 'source_sha256': digest(__file__), 'first_audit_sha256': digest(source),
              'controls': controls, 'rows': rows,
              'scope': '精确二进制64射线奇偶与材料直线见证对应；不证明整个网格嵌入、所有材料连通性或临床精度'}
    with output.open('x', encoding='utf-8') as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
    print(json.dumps({'rows': len(rows), 'connected_witnesses': sum(x['path_connects_small_and_large_interiors'] for x in rows)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
