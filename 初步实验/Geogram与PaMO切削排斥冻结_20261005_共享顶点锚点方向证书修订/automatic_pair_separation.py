"""累计切削排斥投影的自动原始面分离提案，最终仍需全网格精确审计。"""

from fractions import Fraction
import hashlib
import json
import numpy as np
import trimesh
from scipy.optimize import LinearConstraint, minimize
from cut_exclusion import dot_intervals, supporting_planes, face_separators, certify_face_support
from exact_embedding_gate import mesh_valid_full_embedding
from locality_masks import save_obj_fp64
from run_geometry_study import execute

PAIR_CHECKER = '/root/autodl-tmp/graduation_project/constrained_20261005_归一化精度候选与自交面号定位_f8be359dcba4/pairs'
PAIR_CHECKER_SHA = '1537bebe89dfb2c2b2ab8a70b6331af3a02ec680a3d3b38d199f0ca7454c4127'


def exact_pair_separated(triangles, normal, offset):
    """精确核对完整两面分别位于冻结平面两侧，不用浮点间隙代替证据。"""
    n = [Fraction(float(x)) for x in normal]
    h = Fraction(float(offset))
    dot = lambda point: sum(a * Fraction(float(b)) for a, b in zip(n, point))
    return all(dot(p) <= h for p in triangles[0]) and all(dot(p) >= h for p in triangles[1])


def original_pair_separator(a, b):
    """用原始合法面法向和边叉积寻找严格分离，不能分离时保留拒绝。"""
    ae, be = np.roll(a, -1, axis=0) - a, np.roll(b, -1, axis=0) - b
    axes = [np.cross(ae[0], ae[1]), np.cross(be[0], be[1])] + [np.cross(x, y) for x in ae for y in be]
    best = None
    for axis in axes:
        length = np.linalg.norm(axis)
        if length == 0 or not np.isfinite(length):
            continue
        for n in (axis / length, -axis / length):
            _, upper = dot_intervals(a, n[None, :])
            lower, _ = dot_intervals(b, n[None, :])
            low, high = upper.max(), lower.min()
            if high <= low:
                continue
            h = low + (high - low) * .5
            if exact_pair_separated((a, b), n, h) and (best is None or high - low > best['gap_mm']):
                best = {'normal': n.tolist(), 'offset': float(h), 'gap_mm': float(high - low)}
    return best


def original_shared_vertex_separator(a, b, anchor):
    """原始合法面仅共享单点时，寻找两侧其余顶点的严格方向。"""
    vectors = np.vstack([anchor - a, b - anchor])
    lengths = np.linalg.norm(vectors, axis=1)
    vectors = vectors[lengths > 0] / lengths[lengths > 0, None]
    if len(vectors) != 4:
        return None
    result = minimize(lambda n: .5 * float(n @ n), np.zeros(3), jac=lambda n: n,
                      method='SLSQP', constraints=[LinearConstraint(vectors, 1., np.inf)],
                      options={'ftol': 1e-15, 'maxiter': 100})
    # 方向求解的退出码不是几何证书；有限非零提案只按后续精确严格侧证书接受。
    if not np.isfinite(result.x).all() or np.linalg.norm(result.x) == 0:
        return None
    normal = result.x / np.linalg.norm(result.x)
    if not exact_shared_vertex_separated((a, b), normal, anchor):
        return None
    return {'normal': normal.tolist(), 'shared_anchor': np.asarray(anchor).tolist(), 'separator_kind': 'shared_single_vertex'}


def exact_shared_vertex_separated(triangles, normal, anchor):
    """精确验证只有锚点在平面上，两面其余顶点严格处于相反侧。"""
    n = [Fraction(float(x)) for x in normal]
    origin = [Fraction(float(x)) for x in anchor]
    def values(triangle):
        return [sum(a * (Fraction(float(x)) - o) for a, x, o in zip(n, p, origin)) for p in triangle]
    # 零平面值必须来自同一实际锚点，不能把任意共面点当共享拓扑点。
    if any(sum(np.array_equal(point, anchor) for point in triangle) != 1 for triangle in triangles):
        return False
    left, right = values(triangles[0]), values(triangles[1])
    return left.count(0) == 1 and right.count(0) == 1 and all(x <= 0 for x in left) and all(x >= 0 for x in right)


def project_vertices(raw, constraints, budget_mm, fixed_vertices=None):
    """最小位移逐顶点凸投影，超过算法信赖半径或残差不可信时拒绝。"""
    vertices = raw.vertices.copy()
    fixed_vertices = {} if fixed_vertices is None else fixed_vertices
    for index, items in enumerate(constraints):
        matrix, right = np.array([r[0] for r in items]), np.array([r[1] for r in items])
        bounds = right - matrix @ raw.vertices[index]
        # 锚点采用首次工具投影的合法位置，不能同时要求同一顶点处于平面两侧。
        if index in fixed_vertices:
            value = np.asarray(fixed_vertices[index])
            if np.max(right - matrix @ value, initial=0) > 1e-10 or np.linalg.norm(value - raw.vertices[index]) > budget_mm:
                return None, {'reason': 'fixed_shared_anchor_conflicts_with_constraints', 'failed_vertex': index}
            vertices[index] = value
            continue
        if np.all(bounds <= 0):
            continue
        result = minimize(lambda d: .5 * float(d @ d), np.zeros(3), jac=lambda d: d, method='SLSQP',
                          constraints=[LinearConstraint(matrix, bounds, np.inf)], options={'ftol': 1e-15, 'maxiter': 100})
        if not result.success or np.max(bounds - matrix @ result.x, initial=0) > 1e-10 or np.linalg.norm(result.x) > budget_mm:
            return None, {'reason': 'infeasible_or_unverified_projection', 'failed_vertex': index,
                          'solver_message': result.message, 'displacement_mm': float(np.linalg.norm(result.x))}
        vertices[index] += result.x
    return trimesh.Trimesh(vertices, raw.faces.copy(), process=False), None


def repair_with_automatic_pair_guard(raw, tools, side, budget_mm=.3, max_rounds=3):
    """自动精确发现当前相交对，累加原始面分离约束；不硬编码案例或面号。"""
    record = {'accepted': False, 'budget_mm': budget_mm, 'cumulative_tools': len(tools), 'max_added_rounds': max_rounds,
              'rounds': [], 'proposal_role': 'automatic_original_pair_separation', 'movement_CCD_certified': False}
    initial = side.classify(raw, [raw.vertices.mean(axis=0)])
    valid, metrics = mesh_valid_full_embedding(raw, initial)
    record.update(raw_saved_mesh_sha256=initial.get('saved_mesh_sha256'), raw_metrics=metrics)
    if not valid:
        record['reason'] = 'raw_mesh_not_valid_embedded_source_for_separation'
        return raw.copy(), record
    engine = side.engine
    if execute(engine.client, ['sha256sum', PAIR_CHECKER])['stdout'].split()[0] != PAIR_CHECKER_SHA:
        raise ValueError('精确自交面号二进制摘要改变')
    normals, offsets, choices = [], [], []
    constraints = [[] for _ in raw.vertices]
    for tool in tools:
        n, h = supporting_planes(tool)
        selected, _ = face_separators(raw, tool)
        normals.append(n)
        offsets.append(h)
        choices.append(selected)
        for vertex, owners in enumerate(raw.vertex_faces):
            for plane in np.unique(selected[owners[owners >= 0]]):
                constraints[vertex].append((n[plane], h[plane] + 1e-8))
    pairs, fixed_vertices = {}, {}
    for round_id in range(max_rounds + 1):
        candidate, failure = project_vertices(raw, constraints, budget_mm, fixed_vertices)
        if failure:
            record.update(failure)
            return raw.copy(), record
        side.counter += 1
        path = engine.output / ('pair_guard_' + str(side.counter) + '.obj')
        save_obj_fp64(candidate, path)
        saved = trimesh.load(path, process=False)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        remote = engine.remote + '/' + path.name
        engine.sftp.put(str(path), remote)
        if execute(engine.client, ['sha256sum', remote])['stdout'].split()[0] != digest:
            raise ValueError('自动面分离精确审计保存对象摘要不匹配')
        run = execute(engine.client, [PAIR_CHECKER, remote], timeout=120)
        if run['returncode']:
            record.update(reason='exact_pairs_execution_failed', execution=run)
            return raw.copy(), record
        audit = json.loads(run['stdout'])
        record['rounds'].append({'round': round_id, 'candidate_sha256': digest, 'added_constraints': len(pairs), 'exact_audit': audit})
        if audit.get('embedded_closed'):
            face_certificates = [certify_face_support(saved, n, h, selected) for n, h, selected in zip(normals, offsets, choices)]
            pair_certificates = [{'face_ids': list(ids), 'passed': (exact_shared_vertex_separated(saved.triangles[list(ids)], p['normal'], p['shared_anchor']) if p.get('separator_kind') == 'shared_single_vertex' else exact_pair_separated(saved.triangles[list(ids)], p['normal'], p['offset']))}
                                 for ids, p in pairs.items()]
            anchors = [side.anchor(saved, tool, n, h) for tool, n, h in zip(tools, normals, offsets)]
            valid, metrics = mesh_valid_full_embedding(saved, anchors[0]['classification'])
            same_topology = saved.euler_number == raw.euler_number and len(saved.split(only_watertight=False)) == len(raw.split(only_watertight=False))
            bound = Fraction(str(budget_mm)) ** 2
            displacement_ok = all(sum((Fraction(float(a)) - Fraction(float(b))) ** 2 for a, b in zip(p, old)) <= bound
                                  for p, old in zip(saved.vertices, raw.vertices))
            accepted = bool(valid and same_topology and displacement_ok and all(c['passed'] for c in face_certificates + pair_certificates + anchors))
            record.update(accepted=accepted, candidate_sha256=digest, metrics=metrics, same_topology=same_topology,
                          face_support_certificate=face_certificates, outside_anchor_certificate=anchors,
                          pair_separation_certificate=pair_certificates, exact_displacement_bound_passed=displacement_ok,
                          faces_exact=bool(np.array_equal(saved.faces, raw.faces)),
                          moved_vertices=int(np.any(saved.vertices != raw.vertices, axis=1).sum()),
                          max_displacement_mm=float(np.linalg.norm(saved.vertices - raw.vertices, axis=1).max()),
                          original_pair_separators=[{'face_ids': list(ids), **p} for ids, p in pairs.items()])
            return (saved if accepted else raw.copy()), record
        discovered = audit.get('pair_face_ids_zero_based', [])
        if not discovered or len(discovered) != audit.get('self_intersection_pairs') or round_id == max_rounds:
            record['reason'] = 'incomplete_pair_list_or_added_round_budget_exhausted'
            return raw.copy(), record
        added = 0
        for ids in discovered:
            ids = tuple(ids)
            if ids in pairs:
                continue
            shared = np.intersect1d(raw.faces[ids[0]], raw.faces[ids[1]])
            if len(shared) == 1:
                vertex = int(shared[0])
                separator = original_shared_vertex_separator(*raw.triangles[list(ids)], raw.vertices[vertex])
                if separator is None:
                    record.update(reason='no_exact_shared_vertex_separator', failed_pair=list(ids))
                    return raw.copy(), record
                # 只冻结首次合法工具投影位置，不冻结未满足工具约束的原始点。
                fixed_vertices.setdefault(vertex, candidate.vertices[vertex].copy())
                anchor = fixed_vertices[vertex]
                separator.update(shared_anchor=anchor.tolist(), shared_vertex_id=vertex)
                n = np.asarray(separator['normal'])
                h = float(n @ anchor)
                for item in raw.faces[ids[0]]:
                    if int(item) != vertex:
                        constraints[item].append((-n, -h + 1e-8))
                for item in raw.faces[ids[1]]:
                    if int(item) != vertex:
                        constraints[item].append((n, h + 1e-8))
            else:
                separator = original_pair_separator(*raw.triangles[list(ids)])
                if separator is None:
                    record.update(reason='no_strict_original_pair_separator', failed_pair=list(ids))
                    return raw.copy(), record
                n, h = np.asarray(separator['normal']), separator['offset']
                # 无共享点沿用原固定面分离方式与原间隙；共享边尚不放宽为例外。
                for vertex in raw.faces[ids[0]]:
                    constraints[vertex].append((-n, -h + 1e-8))
                for vertex in raw.faces[ids[1]]:
                    constraints[vertex].append((n, h + 1e-8))
            pairs[ids] = separator
            added += 1
        if added == 0:
            record['reason'] = 'exact_collisions_persist_without_new_pairs'
            return raw.copy(), record

