"""为不同三角化提供保守的双向距离上界；未能证明时返回不成立。"""
from collections import Counter, defaultdict
from fractions import Fraction
from math import inf, nextafter, sqrt
from itertools import product
import numpy as np


def triangle_rows(vertices, faces, bits):
    # 来源长度和真实索引必须成立，不能因zip截断或负索引漏掉待比较的面。
    if len(faces) != len(bits) or np.asarray(faces).shape != (len(faces), 3):
        raise ValueError('三角面与来源长度或维度不一致')
    if np.any(faces < 0) or np.any(faces >= len(vertices)) or not np.isfinite(vertices).all():
        raise ValueError('坐标或三角面索引非法')
    rows = Counter()
    for triangle, label in zip(vertices[faces], bits):
        points = tuple(tuple(map(float, point)) for point in triangle)
        rows[(min(points[k:] + points[:k] for k in range(3)), int(label))] += 1
    return rows


def certify_correspondence(old_vertices, old_faces, old_bits, new_vertices, new_faces, new_bits, tolerance_mm=1e-10):
    """相同有向边界和同向投影给出相同投影覆盖，再以精确离面高度约束提升距离。"""
    old = triangle_rows(old_vertices, old_faces, old_bits)
    new = triangle_rows(new_vertices, new_faces, new_bits)
    common = old & new
    old.subtract(common)
    new.subtract(common)
    differences = [(mode, points, label) for mode, rows in enumerate((old, new))
                   for (points, label), count in rows.items() for _ in range(count) if count > 0]
    if not differences:
        return dict(accepted=True, exactly_same_oriented_triangles=True, error_upper_mm=0.0, patches=[])
    owners = defaultdict(list)
    for index, (_, points, label) in enumerate(differences):
        for point in points:
            owners[(label, point)].append(index)
    pending = set(range(len(differences)))
    patches = []
    while pending:
        seed = min(pending)
        group, queue = set(), [seed]
        while queue:
            index = queue.pop()
            if index in group:
                continue
            group.add(index)
            _, points, label = differences[index]
            for point in points:
                queue.extend(x for x in owners[(label, point)] if x not in group)
        pending.difference_update(group)
        selected = [differences[i] for i in sorted(group)]
        points = sorted({point for _, triangle, _ in selected for point in triangle})
        ratios = {point: [value.as_integer_ratio() for value in point] for point in points}
        denominator = max(d for row in ratios.values() for _, d in row)
        integer = {point: tuple(n * (denominator // d) for n, d in ratios[point]) for point in points}
        origin = integer[selected[0][1][0]]
        first = [integer[x] for x in selected[0][1]]
        u = [first[1][k] - first[0][k] for k in range(3)]
        v = [first[2][k] - first[0][k] for k in range(3)]
        normal = (u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0])
        if not any(normal):
            return dict(accepted=False, reason='基准三角形退化', completed_patches=patches)
        axis = max(range(3), key=lambda k: abs(normal[k]))
        coordinates = [k for k in range(3) if k != axis]
        signs, boundaries = set(), [Counter(), Counter()]
        for mode, triangle, _ in selected:
            a, b, c = [integer[x] for x in triangle]
            i, j = coordinates
            area = (b[i]-a[i])*(c[j]-a[j]) - (b[j]-a[j])*(c[i]-a[i])
            if area == 0:
                return dict(accepted=False, reason='存在零投影面积，覆盖证明未成立', completed_patches=patches)
            signs.add(1 if area > 0 else -1)
            for k in range(3):
                x, y = triangle[k], triangle[(k+1) % 3]
                edge = tuple(sorted((x, y)))
                boundaries[mode][edge] += 1 if x < y else -1
        if len(signs) != 1:
            return dict(accepted=False, reason='投影存在反向面，覆盖证明未成立', completed_patches=patches)
        boundary = [{edge: count for edge, count in row.items() if count} for row in boundaries]
        if not boundary[0] or boundary[0] != boundary[1]:
            return dict(accepted=False, reason='两侧有向边界不同或局部投影无边界', completed_patches=patches)
        # 同向三角链的边界相同，平面内部的覆盖重数相同；无需用抽样代替覆盖。
        # 每点提升到同一参考平面只沿删除的坐标轴，线性插值不超过顶点最大高度。
        height = max(Fraction(abs(sum(normal[k]*(integer[point][k]-origin[k]) for k in range(3))),
                              abs(normal[axis])*denominator) for point in points)
        bound = 2 * height
        upper = float(bound)
        while Fraction.from_float(upper) < bound:
            upper = nextafter(upper, inf)
        patch = dict(label=selected[0][2], old_triangles=sum(x[0] == 0 for x in selected),
                     new_triangles=sum(x[0] == 1 for x in selected), projection_axis=axis,
                     same_oriented_boundary=True, same_direction_nonzero_projection=True,
                     bound_numerator=str(bound.numerator), bound_denominator=str(bound.denominator),
                     error_upper_mm=upper)
        patches.append(patch)
        if bound > Fraction.from_float(tolerance_mm):
            return dict(accepted=False, reason='距离上界超出指定容差', completed_patches=patches)
    return dict(accepted=True, exactly_same_oriented_triangles=False,
                error_upper_mm=max(p['error_upper_mm'] for p in patches), patches=patches,
                scope='仅两份保存三角面的双向几何上界，不证明嵌入性、布尔真值或连续累计误差')


def certify_with_virtual_snap(old_vertices, old_faces, old_bits, new_vertices, new_faces, new_bits, tolerance_mm=1e-10):
    """仅为比较构造共同辅助面；原始数组保持，并计入两侧全部虚拟移动距离。"""
    direct = certify_correspondence(old_vertices, old_faces, old_bits, new_vertices, new_faces, new_bits, tolerance_mm)
    if direct['accepted']:
        return direct
    old, new = triangle_rows(old_vertices, old_faces, old_bits), triangle_rows(new_vertices, new_faces, new_bits)
    common = old & new
    differences = (old - common) | (new - common)
    points = sorted({point for triangle, _ in differences for point in triangle})
    radius = Fraction.from_float(tolerance_mm) / 4
    if radius <= 0:
        return dict(accepted=False, reason='辅助比较需要正容差', direct=direct)
    buckets, mapping, movement = defaultdict(list), {}, Fraction(0)
    for point in points:
        cell = tuple(Fraction.from_float(x) // radius for x in point)
        representative, displacement = point, Fraction(0)
        for offset in product((-1, 0, 1), repeat=3):
            neighbor = tuple(cell[k]+offset[k] for k in range(3))
            for candidate in buckets[neighbor]:
                squared = sum((Fraction.from_float(point[k])-Fraction.from_float(candidate[k]))**2 for k in range(3))
                if squared <= radius**2:
                    representative, displacement = candidate, squared
                    break
            if representative != point:
                break
        mapping[point] = representative
        movement = max(movement, displacement)
        if representative == point:
            buckets[cell].append(point)
    if not movement:
        return dict(accepted=False, reason='没有可构造的有界辅助合并', direct=direct)
    auxiliary = []
    for vertices, faces, bits in [(old_vertices, old_faces, old_bits), (new_vertices, new_faces, new_bits)]:
        v = vertices.copy()
        for point, representative in mapping.items():
            if representative != point:
                mask = np.all(vertices == point, axis=1)
                v[mask] = representative
        triangles = v[faces]
        collapsed = (np.all(triangles[:, 0] == triangles[:, 1], axis=1) |
                     np.all(triangles[:, 1] == triangles[:, 2], axis=1) |
                     np.all(triangles[:, 2] == triangles[:, 0], axis=1))
        retained, retained_bits = triangles[~collapsed], bits[~collapsed]
        for index in np.flatnonzero(collapsed):
            image = sorted(set(map(tuple, triangles[index])))
            support = retained[retained_bits == bits[index]]
            # 点映像和完整线段必须位于同来源保留面的声明顶点/边，不能直接忽略细长面。
            owners = np.ones(len(support), dtype=bool)
            for point in image:
                owners &= np.any(np.all(support == point, axis=2), axis=1)
            if not np.any(owners):
                return dict(accepted=False, reason='辅助退化映像缺少同来源完整覆盖', direct=direct)
        auxiliary.append((v, faces[~collapsed], bits[~collapsed]))
    projection = certify_correspondence(*auxiliary[0], *auxiliary[1], tolerance_mm)
    if not projection['accepted']:
        return dict(accepted=False, reason='辅助面仍未取得投影覆盖证书', direct=direct, projection=projection)
    delta = nextafter(sqrt(float(movement)), inf)
    while Fraction.from_float(delta)**2 < movement:
        delta = nextafter(delta, inf)
    # 每个原三角形与其辅助三角形按相同重心权重对应，两侧各付一次最大顶点距离。
    bound = 2 * Fraction.from_float(delta) + Fraction.from_float(projection['error_upper_mm'])
    upper = float(bound)
    while Fraction.from_float(upper) < bound:
        upper = nextafter(upper, inf)
    return dict(accepted=bound <= Fraction.from_float(tolerance_mm), virtual_only=True,
                error_upper_mm=upper, bound_numerator=str(bound.numerator), bound_denominator=str(bound.denominator),
                vertex_move_squared_numerator=str(movement.numerator), vertex_move_squared_denominator=str(movement.denominator),
                direct=direct, projection=projection,
                scope='仅保存对象双向几何上界；辅助面不发布，不证明嵌入或布尔真值，不是连续误差证书')
