"""固定原始共边的局部替换实验；候选先验收，不把拼接成功等同于质量合格。"""
from pathlib import Path
import sys
import numpy as np
import triangle
import trimesh
from pymeshlab_isolation import self_intersection_flags

sys.path.insert(0, str(Path(__file__).parents[1]/'真实骨面高度图验证'))
from projection import ProjectedSurface, load_bone
from surface_patch import verify_chart, overlay_error
from real_patch import BoneChart, Rejected, mesh_quality


def edges_of(faces):
    """返回无向边及邻面数，拼接检查使用索引而非空间距离焊接。"""
    edges = np.sort(np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]]), axis=1)
    return np.unique(edges, axis=0, return_counts=True)


def boundary_of(faces):
    edges, counts = edges_of(faces)
    boundary = edges[counts == 1]
    ids, degrees = np.unique(boundary, return_counts=True)
    if np.any(counts > 2) or np.any(degrees != 2) or len(np.unique(faces))-len(edges)+len(faces) != 1:
        raise Rejected('替换域不是具有单一闭合边界的三角盘')
    # 欧拉示性数之外显式遍历连通性，排除多个分离分量。
    seen, pending = set(), [int(ids[0])]
    adjacency = {int(i): [] for i in ids}
    for a, b in boundary:
        adjacency[int(a)].append(int(b))
        adjacency[int(b)].append(int(a))
    while pending:
        current = pending.pop()
        if current not in seen:
            seen.add(current)
            pending.extend(adjacency[current])
    if len(seen) != len(ids):
        raise Rejected('替换域存在多个边界环')
    return boundary


def stitch_candidate(source, removed, chart, area, graded=False, extra_points=None):
    """保留外边界；允许新实验补充内部误差采样点，默认保持原对照行为。"""
    boundary = boundary_of(source.faces[removed])
    source_ids = np.unique(boundary)
    segments = np.searchsorted(source_ids, boundary)
    points = source.vertices[source_ids, :2]
    options = f'pq30Ya{area:.8f}QS200000'
    if graded:
        from patch_model import lattice
        import matplotlib.tri as mtri
        interior, _ = lattice(np.sqrt(4*area/np.sqrt(3)), half_width=4.)
        interior = interior[np.linalg.norm(interior, axis=1) < 4.]
        finder = mtri.Triangulation(source.vertices[:, 0], source.vertices[:, 1],
                                   source.faces[removed]).get_trifinder()
        interior = interior[finder(interior[:, 0], interior[:, 1]) >= 0]
        points = np.vstack([points, interior])
        options = 'pq30YQS200000'
    if extra_points is not None and len(extra_points):
        points = np.vstack([points, extra_points])
    result = triangle.triangulate(dict(vertices=points, segments=segments), options)
    xy, faces = result['vertices'], result['triangles']
    if not np.array_equal(xy[:len(source_ids)], source.vertices[source_ids, :2]):
        raise Rejected('三角化改变原边界顶点或排序')
    actual_boundary = boundary_of(faces)
    if set(map(tuple, actual_boundary)) != set(map(tuple, np.sort(segments, axis=1))):
        raise Rejected('三角化改变外边界线段，禁止产生T形接缝')
    vertices = np.column_stack([xy, chart.height(xy)])
    vertices[:len(source_ids)] = source.vertices[source_ids]
    # 复用原顶点索引；新增顶点追加，未修改面逐项原样保留。
    mapping = np.r_[source_ids, np.arange(len(source.vertices), len(source.vertices)+len(xy)-len(source_ids))]
    keep = np.ones(len(source.faces), dtype=bool)
    keep[removed] = False
    whole_vertices = np.vstack([source.vertices, vertices[len(source_ids):]])
    whole_faces = np.vstack([source.faces[keep], mapping[faces]])
    whole = trimesh.Trimesh(whole_vertices, whole_faces, process=False)
    return dict(vertices=vertices, faces=faces, whole=whole, mapping=mapping,
                source_ids=source_ids, boundary=boundary, keep=keep)


def topology(mesh):
    """欧拉数仅计被引用顶点，避免删除局部面后遗留孤立原顶点影响统计。"""
    edges, counts = edges_of(mesh.faces)
    return dict(watertight=bool(mesh.is_watertight), winding=bool(mesh.is_winding_consistent),
                euler=int(len(np.unique(mesh.faces))-len(edges)+len(mesh.faces)),
                boundary_edges=int(np.sum(counts == 1)), nonmanifold_edges=int(np.sum(counts > 2)))


def audit_candidate(surface, candidate):
    """集中执行全部门槛，调用方不能误用未完成自交检查的通过标志。"""
    vertices, faces = candidate['vertices'], candidate['faces']
    q, angles, areas = mesh_quality(vertices, faces)
    error, coverage = overlay_error(surface, vertices, faces)
    seam = np.any(faces < len(candidate['source_ids']), axis=1)
    result = topology(candidate['whole'])
    # 保留检测器报警；浮点接触报警未经复核不能解释为真实穿插。
    flags = self_intersection_flags(candidate['whole'].vertices, candidate['whole'].faces)
    candidate['intersection_flags'] = flags
    result['self_intersection_flags'] = int(flags.sum())
    result['new_face_intersection_flags'] = int(flags[candidate['keep'].sum():].sum())
    result.update(faces=len(faces), vertices=len(vertices), min_q=float(q.min()),
                  min_angle_deg=float(angles.min()), degenerate=int(np.sum(areas <= 1e-12)),
                  bad_faces=int(np.sum((q < .4) | (angles < 25))),
                  seam_faces=int(seam.sum()), seam_min_angle_deg=float(angles[seam].min()),
                  error_max_mm=float(error.max()), coverage_max_mm2=float(coverage.max()),
                  largest_triangle_area_mm2=float(areas.max()/2),
                  error_mean_mm=float(error.mean()), error_p95_mm=float(np.percentile(error, 95)),
                  error_p99_mm=float(np.percentile(error, 99)),
                  seam_error_max_mm=float(error[seam].max()))
    result['accepted'] = bool(result['watertight'] and result['winding'] and
                              result['euler'] == surface.mesh.euler_number and
                              not result['nonmanifold_edges'] and not result['degenerate'] and
                              not result['bad_faces'] and not result['self_intersection_flags'] and
                              error.max() <= .1 and coverage.max() <= 1e-7)
    return result, error, angles
