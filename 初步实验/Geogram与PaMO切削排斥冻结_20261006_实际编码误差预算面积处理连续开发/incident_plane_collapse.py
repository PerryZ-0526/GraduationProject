"""端点折叠失败后，沿原短边寻找满足两侧邻面原预算的内部位置。"""
import numpy as np
from scipy.optimize import minimize, LinearConstraint
import trimesh
import guarded_source_sliver_collapse as original
from locality_retriangulate import invalid_faces


def balanced_parameter(edge, normals, on_a, tolerance=1e-8):
    coefficients = np.abs(normals @ edge)
    a = float(coefficients[on_a].max(initial=0))
    b = float(coefficients[~on_a].max(initial=0))
    # 两侧最大平面偏移分别为t*a与(1-t)*b，交点给出确定性最小最大偏移位置。
    t = b / (a + b) if a + b else .5
    return t if max(t * a, (1 - t) * b) <= tolerance else None



def incident_plane_point(a, b, normals, old_points, tolerance=1e-8):
    center = a + .5 * (b - a)
    radius = float(np.linalg.norm(b - a))
    if radius == 0:
        return None
    # 以原边长度缩放局部坐标，避免世界坐标与1e-8平面约束的量级差导致优化误判。
    offsets = np.sum((old_points - center) * normals, axis=1) / radius
    slack = tolerance * (1 - 1e-6) / radius
    result = minimize(lambda y: .5 * float(y @ y), np.zeros(3), jac=lambda y: y,
        constraints=[LinearConstraint(normals, offsets - slack, offsets + slack)],
        method='SLSQP', options={'ftol': 1e-15, 'maxiter': 100})
    if not result.success:
        return None
    point = center + radius * result.x
    # 合并点到每个原端点的位移不超过原短边长度，最终保存点仍重核原平面预算。
    if max(np.linalg.norm(point - a), np.linalg.norm(point - b)) > radius:
        return None
    return point


def collapse_degenerate(mesh, bits, allow_shared=False, allow_small_incident=False, candidate_guard=None):
    before = original.invalid_faces
    try:
        # 原端点机制先尝试，成功结果与预算保持；本模块仅补其未解决部分。
        original.invalid_faces = invalid_faces
        candidate, labels, baseline = original.collapse_degenerate(mesh, bits, allow_shared, allow_small_incident, candidate_guard)
    finally:
        original.invalid_faces = before
    vertices, faces = candidate.vertices.copy(), candidate.faces.copy()
    labels = np.asarray(labels).copy()
    remaining = int(invalid_faces(vertices, faces).sum())
    record = {'original_endpoint_proposal': baseline, 'initial_remaining_invalid_faces': remaining,
              'max_interior_collapses': remaining, 'plane_tolerance_mm': 1e-8, 'interior_collapses': [], 'rejections': {},
              'scope': '同一原短边内部位置，原来源和最终嵌入审计仍必须通过'}
    def reject(reason):
        record['rejections'][reason] = record['rejections'].get(reason, 0) + 1
    for _ in range(remaining):
        bad = invalid_faces(vertices, faces)
        pairs = np.sort(np.concatenate([faces[bad][:, [0, 1]], faces[bad][:, [1, 2]], faces[bad][:, [2, 0]]]), axis=1)
        edges = np.unique(pairs, axis=0)
        order = np.argsort(np.linalg.norm(vertices[edges[:, 0]] - vertices[edges[:, 1]], axis=1), kind='stable')
        committed = False
        for a, b in edges[order]:
            a, b = int(a), int(b)
            shared = np.sum(np.isin(faces, [a, b]), axis=1) == 2
            if int(shared.sum()) != 2:
                reject('two_shared_faces'); continue
            neighbors_a = set(faces[np.any(faces == a, axis=1)].ravel()) - {a}
            neighbors_b = set(faces[np.any(faces == b, axis=1)].ravel()) - {b}
            if neighbors_a & neighbors_b != set(faces[shared].ravel()) - {a, b}:
                reject('link_condition'); continue
            # 移动两个端点合并为一处，必须核对两端全部关联面，不能只检查被删除端。
            changed = np.any(np.isin(faces, [a, b]), axis=1) & ~shared
            old = vertices[faces[changed]]
            normals = np.cross(old[:, 1] - old[:, 0], old[:, 2] - old[:, 0])
            lengths = np.linalg.norm(normals, axis=1)
            if not len(lengths):
                reject('empty_incident'); continue
            small = lengths <= 2e-12
            if small.any() and not allow_small_incident:
                reject('small_incident_disabled'); continue
            normals[~small] /= lengths[~small, None]
            if small.any():
                stable = [original.exact_unit_normal(t) for t in old[small]]
                if any(n is None for n in stable):
                    reject('exact_collinear_incident'); continue
                normals[small] = stable
            t = balanced_parameter(vertices[b] - vertices[a], normals, np.any(faces[changed] == a, axis=1))
            placement = 'original_edge_internal_position'
            if t is None:
                # 原边上无可行位置才补邻面约束的三维最小位移解，不放宽原平面预算。
                point = incident_plane_point(vertices[a], vertices[b], normals, old[:, 0])
                placement = 'same_incident_plane_budget_local_3D_position'
                if point is None:
                    reject('no_feasible_incident_plane_position'); continue
            else:
                point = vertices[a] + t * (vertices[b] - vertices[a])
            deviations = np.abs(np.sum((point - old[:, 0]) * normals, axis=1))
            if np.any(deviations > 1e-8):
                reject('actual_saved_point_plane_deviation'); continue
            replacement = faces.copy()
            replacement[replacement == b] = a
            keep = ~shared
            new_faces = replacement[keep]
            if len(np.unique(np.sort(new_faces, axis=1), axis=0)) != len(new_faces):
                reject('duplicate_face'); continue
            new_vertices = vertices.copy()
            new_vertices[a] = point
            new = new_vertices[replacement[changed]]
            new_normals = np.cross(new[:, 1] - new[:, 0], new[:, 2] - new[:, 0])
            if np.any(np.sum(new_normals * normals, axis=1) <= np.where(small, 0., 2e-12)):
                reject('orientation_or_projected_area'); continue
            changed_bad = invalid_faces(new_vertices, replacement[changed])
            if (changed_bad & ~bad[changed]).any() or int(invalid_faces(new_vertices, new_faces).sum()) >= int(bad.sum()):
                reject('no_strict_bad_face_reduction'); continue
            proposed = trimesh.Trimesh(new_vertices, new_faces, process=False)
            if candidate_guard is not None and not candidate_guard(proposed, labels[keep]):
                reject('parent_and_tool_provenance_guard'); continue
            displacement = max(float(np.linalg.norm(point - vertices[a])), float(np.linalg.norm(point - vertices[b])))
            vertices, faces, labels = new_vertices, new_faces, labels[keep]
            record['interior_collapses'].append({'edge': [a, b], 'parameter': t, 'placement': placement, 'point_mm': point.tolist(),
                'max_endpoint_displacement_mm': displacement, 'max_incident_plane_deviation_mm': float(deviations.max()),
                'remaining_invalid_faces': int(invalid_faces(vertices, faces).sum())})
            committed = True
            break
        if not committed:
            break
    result = trimesh.Trimesh(vertices, faces, process=False)
    result.remove_unreferenced_vertices()
    record['remaining_invalid_faces'] = int(invalid_faces(result.vertices, result.faces).sum())
    return result, labels, record
