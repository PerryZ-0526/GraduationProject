"""按实际原点编码反向面触发既有碎片操作，保留来源和物理几何约束。"""

import numpy as np
import locality_retriangulate
import incident_plane_collapse as locality_sliver_collapse
from native_fp32_fragment_guard import native_fp32_invalid_faces
from geometry_preservation_audit import MeshDistance
from audit_pamo_outputs import as_polydata
from canonical_clean_source import canonical_clean_source


def encoded_orientation_risk(vertices, faces, origin):
    # 除已有零面积判定外，检查编码后仍有正面积但方向反转的面。
    result = native_fp32_invalid_faces(vertices, faces)
    physical = np.asarray(vertices, np.float64)[faces]
    encoded = np.asarray(np.asarray(vertices, np.float64) - origin, np.float32)[faces]
    n = np.cross(physical[:, 1] - physical[:, 0], physical[:, 2] - physical[:, 0])
    # 原物理审查允许正面积，新增与最终输出一致的小面积触发，不放宽来源平面约束。
    result |= .5 * np.linalg.norm(n, axis=1) <= 1e-12
    for coordinates in (encoded, encoded.astype(np.float64)):
        q = np.cross(coordinates[:, 1] - coordinates[:, 0], coordinates[:, 2] - coordinates[:, 0])
        result |= np.sum(n * q.astype(np.float64), axis=1) <= 0
    return result


def prepare_encoded_orientation_source(mesh, bits, audit, candidate_guard=None):
    # 本次操作固定原源实际三角均值原点，最终候选须重新计算原点并完整门控。
    origin = np.asarray(mesh.vertices, np.float64)[mesh.faces].mean(axis=1).mean(axis=0)
    detector = lambda vertices, faces: encoded_orientation_risk(vertices, faces, origin)
    bits = np.asarray(bits)
    candidate, labels = mesh.copy(), bits.copy()
    initial = int(detector(candidate.vertices, candidate.faces).sum())
    record = {"fixed_operation_origin_mm": origin.tolist(), "detector": "old_degenerate_or_physical_area_below_final_floor_or_actual_origin_encoded_normal_nonpositive", "initial_actual_origin_detector_risk_faces": initial, "steps": [],
              "actual_GPU_working_sources_still_required": True, "accepted_for_full_solver": False}
    modules = (locality_retriangulate, locality_sliver_collapse)
    previous = [module.invalid_faces for module in modules]
    try:
        # 只沿用已见翻边—折叠—翻边固定预算、同来源和原几何约束，不增加尝试。
        for module in modules:
            module.invalid_faces = detector
        if initial:
            operations = (locality_retriangulate.repair_degenerate,
                          locality_sliver_collapse.collapse_degenerate,
                          locality_retriangulate.repair_degenerate)
            for operation in operations:
                kwargs = {"allow_shared": True}
                if operation is locality_sliver_collapse.collapse_degenerate:
                    kwargs["allow_small_incident"] = True
                    kwargs["candidate_guard"] = candidate_guard
                candidate, labels, details = operation(candidate, labels, **kwargs)
                record["steps"].append({"operation": operation.__name__, "details": details})
                if not detector(candidate.vertices, candidate.faces).any():
                    break
    finally:
        for module, original in zip(modules, previous):
            module.invalid_faces = original
    valid, metrics = audit(candidate)
    topology = (candidate.is_watertight == mesh.is_watertight and
                candidate.is_winding_consistent == mesh.is_winding_consistent and
                candidate.euler_number == mesh.euler_number and
                len(candidate.split(only_watertight=False)) == len(mesh.split(only_watertight=False)))
    forward = MeshDistance(as_polydata(mesh))(np.vstack([candidate.vertices, candidate.triangles_center]))
    reverse = MeshDistance(as_polydata(candidate))(np.vstack([mesh.vertices, mesh.triangles_center]))
    distance = max(float(forward.max(initial=0)), float(reverse.max(initial=0)))
    # 物理小面未消除时不能进入无重建阶段二三；单独标记原阶段一恢复资格，输出面积下限保留。
    physical_small = int((candidate.area_faces <= 1e-12).sum())
    pending = bool(valid and topology and distance <= 1e-7 and physical_small == 0)
    # 输入只要求正面积和完整合法；残余小面必须经原阶段一重建，最终面积下限不改。
    stage1_ready = bool(valid and topology and distance <= 1e-7 and physical_small > 0)
    record["physical_candidate_ready_for_full_stage1_encoding_gate"] = stage1_ready
    record["selected_use_stage1"] = stage1_ready
    record["remaining_physical_small_faces"] = physical_small
    record.update(physical_audit=metrics, topology_preserved=bool(topology), geometry_probe_max_mm=distance,
                  geometry_probe_budget_mm=1e-7, continuous_geometry_certified=False,
                  remaining_fixed_origin_detector_risk_faces=int(detector(candidate.vertices, candidate.faces).sum()),
                  physical_candidate_ready_for_actual_encoding_gate=pending)
    # 固定原点风险只用于触发，最终动态原点的三份实际工作源仍须完整检查。
    result, result_bits = (candidate, labels) if pending or stage1_ready else (mesh.copy(), bits.copy())
    result, result_bits, ordering = canonical_clean_source(result, result_bits)
    record["canonical_order"] = ordering
    return result, result_bits, record
