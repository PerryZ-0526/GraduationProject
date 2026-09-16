"""三角骨面质量诊断、局部重网格与交付验收，距离单位为毫米。"""
import time

import numpy as np
import trimesh


def removal_metrics(initial_volume, current, planned_removal):
    """对计划实体求交计量，避免把计划外误切计入完成度。"""
    required = planned_removal.volume()
    if required <= 0:
        raise ValueError("计划去除体积必须大于零")
    remaining = (current ^ planned_removal).volume()
    planned_removed = required - remaining
    total_removed = initial_volume - current.volume()
    return dict(planned_remaining_mm3=remaining, planned_removed_mm3=planned_removed,
                excess_removed_mm3=max(0., total_removed - planned_removed),
                completion_pct=100 * planned_removed / required)


def quality(mesh):
    """形状质量一为等边、零为退化；低分位数反映差面尾部。"""
    tri = mesh.triangles
    lengths2 = np.sum((tri - np.roll(tri, 1, axis=1)) ** 2, axis=2)
    area = mesh.area_faces
    q = np.divide(4 * np.sqrt(3) * area, lengths2.sum(axis=1),
                  out=np.zeros(len(area)), where=lengths2.sum(axis=1) > 0)
    angles = np.degrees(mesh.face_angles.min(axis=1))
    return dict(faces=len(area), vertices=len(mesh.vertices),
                watertight=bool(mesh.is_watertight),
                winding=bool(mesh.is_winding_consistent),
                euler=int(mesh.euler_number), volume_mm3=float(mesh.volume),
                degenerate=int(np.count_nonzero(area <= 1e-12)),
                q_mean=float(q.mean()), q_p05=float(np.percentile(q, 5)),
                q_median=float(np.median(q)), q_min=float(q.min()),
                bad_q_pct=float(100 * np.mean(q < .1)),
                angle_lt5_pct=float(100 * np.mean(angles < 5)),
                angle_min_deg=float(angles.min()))


def surface_distances(source, target, samples=10000, seed=20260907):
    """验证全部顶点及固定种子的面积均匀样本；不是严格豪斯多夫上界。"""
    import vtk
    from vtk.util.numpy_support import numpy_to_vtk, numpy_to_vtkIdTypeArray

    poly = vtk.vtkPolyData()
    points = vtk.vtkPoints()
    points.SetData(numpy_to_vtk(np.asarray(target.vertices), deep=True))
    poly.SetPoints(points)
    cells = vtk.vtkCellArray()
    packed = np.column_stack((np.full(len(target.faces), 3), target.faces))
    cells.SetCells(len(target.faces), numpy_to_vtkIdTypeArray(
        packed.astype(np.int64).ravel(), deep=True))
    poly.SetPolys(cells)
    # 直接查询最近三角形，避免隐式有符号距离在退化参考面处访问异常。
    locator = vtk.vtkStaticCellLocator()
    locator.SetDataSet(poly)
    locator.BuildLocator()
    sampled, _ = trimesh.sample.sample_surface(source, samples, seed=seed)
    queries = np.vstack((source.vertices, sampled))
    closest = [0., 0., 0.]
    cell_id, sub_id, distance2 = vtk.reference(0), vtk.reference(0), vtk.reference(0.)
    distances = np.empty(len(queries))
    for index, point in enumerate(queries):
        locator.FindClosestPoint(point, closest, cell_id, sub_id, distance2)
        distances[index] = np.sqrt(float(distance2))
    return dict(mean_mm=float(distances.mean()), p95_mm=float(np.percentile(distances, 95)),
                p99_mm=float(np.percentile(distances, 99)), max_mm=float(distances.max()),
                over_01mm=int(np.count_nonzero(distances > .1)), queries=len(queries))


def remesh_local(mesh, center, edge_mm=.6, iterations=3, radius_mm=22.,
                 surface_budget_mm=.05, precision64=False, smooth=True):
    """仅维护盂中心邻域；修复限于清理后产生的微小三边孔。"""
    import pymeshlab as pm

    started = time.perf_counter()
    ms = pm.MeshSet()
    ms.add_mesh(pm.Mesh(np.asarray(mesh.vertices), np.asarray(mesh.faces)))
    ms.meshing_remove_duplicate_vertices()
    ms.meshing_remove_null_faces()
    clean = ms.current_mesh()
    cleaned = trimesh.Trimesh(clean.vertex_matrix(), clean.face_matrix(), process=False)
    edges, counts = np.unique(cleaned.edges_sorted, axis=0, return_counts=True)
    boundary = edges[counts == 1]
    if np.any(counts > 2):
        raise ValueError("清理后出现非流形边，停止交付")
    if len(boundary):
        # 仅允许原本水密模型清理产生的微孔，禁止填补真实解剖缺口。
        lengths = np.linalg.norm(cleaned.vertices[boundary[:, 0]] -
                                 cleaned.vertices[boundary[:, 1]], axis=1)
        if not mesh.is_watertight or lengths.max() > .001:
            raise ValueError("清理产生非微小边界，停止自动修复")
        ms.meshing_close_holes(maxholesize=4, refinehole=False)
        repaired = ms.current_mesh()
        if not trimesh.Trimesh(repaired.vertex_matrix(), repaired.face_matrix(),
                               process=False).is_watertight:
            raise ValueError("微孔修复后仍不水密，停止重网格")
    cx, cy, cz = map(float, center)
    expression = " || ".join(
        f"(x{i}-({cx}))^2+(y{i}-({cy}))^2+(z{i}-({cz}))^2<{radius_mm ** 2}"
        for i in range(3))
    ms.compute_selection_by_condition_per_face(condselect=expression)
    ms.meshing_isotropic_explicit_remeshing(
        iterations=iterations, targetlen=pm.PureValue(edge_mm), featuredeg=30.,
        checksurfdist=True, maxsurfdist=pm.PureValue(surface_budget_mm),
        selectedonly=True, smoothflag=smooth)
    result = ms.current_mesh()
    output = trimesh.Trimesh(result.vertex_matrix(), result.face_matrix(), process=False)
    # 动态维护保留双精度，旧分析副本保持原精度；简化后仍须全部验收。
    from real_bone_system_demo import to_manifold, to_trimesh
    output = to_trimesh(to_manifold(output, precision64).simplify(1e-5), precision64)
    return output, (time.perf_counter() - started) * 1000


def validated_delivery(mesh, center, **parameters):
    """输出带验收证据的分析副本，失败时由调用方保留原始骨面。"""
    start = time.perf_counter()
    result, remesh_ms = remesh_local(mesh, center, **parameters)
    before, after = quality(mesh), quality(result)
    import pymeshlab as pm
    check = pm.MeshSet()
    check.add_mesh(pm.Mesh(np.asarray(result.vertices), np.asarray(result.faces)))
    check.compute_selection_by_self_intersections_per_face()
    after['self_intersection_faces'] = check.current_mesh().selected_face_number()
    forward = surface_distances(mesh, result)
    backward = surface_distances(result, mesh)
    delta_volume = abs(result.volume - mesh.volume)
    volume_limit = 5.0
    accepted = (after['watertight'] and after['winding'] and after['self_intersection_faces'] == 0 and
                after['euler'] == before['euler'] and after['degenerate'] == 0 and
                after['bad_q_pct'] < 5 and after['bad_q_pct'] <= before['bad_q_pct'] and
                max(forward['max_mm'], backward['max_mm']) <= .1 and
                delta_volume <= volume_limit)
    evidence = dict(before=before, after=after, forward=forward, backward=backward,
                    remesh_ms=remesh_ms, total_ms=(time.perf_counter()-start)*1000,
                    volume_change_mm3=float(delta_volume),
                    volume_limit_mm3=float(volume_limit), accepted=bool(accepted),
                    parameters=parameters, seed=20260907, samples_per_direction=10000)
    evidence['effective_parameters'] = dict(edge_mm=.6, iterations=3, radius_mm=22.,
                                          surface_budget_mm=.05)
    evidence['effective_parameters'].update(parameters)
    evidence['effective_parameters'].update(feature_deg=30., simplify_mm=1e-5,
                                           micro_boundary_limit_mm=.001)
    return result, evidence
