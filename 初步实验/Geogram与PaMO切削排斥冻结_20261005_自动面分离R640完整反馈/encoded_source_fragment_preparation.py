"""物理碎片候选通过旧几何约束后交给实际编码门控，不将其提前算作接受。"""

import numpy as np
import locality_retriangulate
import locality_sliver_collapse
from native_fp32_fragment_guard import native_fp32_invalid_faces
from geometry_preservation_audit import MeshDistance
from audit_pamo_outputs import as_polydata
from canonical_clean_source import canonical_clean_source


def prepare_encoded_source(mesh, bits, audit):
    bits = np.asarray(bits)
    candidate, labels = mesh.copy(), bits.copy()
    initial = int(native_fp32_invalid_faces(candidate.vertices, candidate.faces).sum())
    record = {"initial_world_detector_risk_faces": initial, "steps": [],
              "actual_GPU_working_sources_still_required": True, "accepted_for_full_solver": False}
    modules = (locality_retriangulate, locality_sliver_collapse)
    previous = [module.invalid_faces for module in modules]
    try:
        # 只沿用已见翻边—折叠—翻边固定预算、同来源和原几何约束，不增加尝试。
        for module in modules:
            module.invalid_faces = native_fp32_invalid_faces
        if initial:
            operations = (locality_retriangulate.repair_degenerate,
                          locality_sliver_collapse.collapse_degenerate,
                          locality_retriangulate.repair_degenerate)
            for operation in operations:
                kwargs = {"allow_shared": True}
                if operation is locality_sliver_collapse.collapse_degenerate:
                    kwargs["allow_small_incident"] = True
                candidate, labels, details = operation(candidate, labels, **kwargs)
                record["steps"].append({"operation": operation.__name__, "details": details})
                if not native_fp32_invalid_faces(candidate.vertices, candidate.faces).any():
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
    pending = bool(valid and topology and distance <= 1e-7)
    record.update(physical_audit=metrics, topology_preserved=bool(topology), geometry_probe_max_mm=distance,
                  geometry_probe_budget_mm=1e-7, continuous_geometry_certified=False,
                  remaining_world_detector_risk_faces=int(native_fp32_invalid_faces(candidate.vertices, candidate.faces).sum()),
                  physical_candidate_ready_for_actual_encoding_gate=pending)
    # 世界FP32残余风险不提前拒绝或接受，真正的三份工作源必须随后完整检查。
    result, result_bits = (candidate, labels) if pending else (mesh.copy(), bits.copy())
    result, result_bits, ordering = canonical_clean_source(result, result_bits)
    record["canonical_order"] = ordering
    return result, result_bits, record
