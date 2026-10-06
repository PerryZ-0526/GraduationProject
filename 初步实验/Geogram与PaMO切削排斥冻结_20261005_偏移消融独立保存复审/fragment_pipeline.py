"""将已有碎片操作组成固定预算流程，失败返回原输入，不发布部分修复。"""

import numpy as np
from locality_retriangulate import invalid_faces, repair_degenerate
from locality_sliver_collapse import collapse_degenerate
from geometry_preservation_audit import mesh_valid, MeshDistance
from audit_pamo_outputs import as_polydata


def repair_input(mesh, bits, audit=mesh_valid, allow_shared=False, allow_small_incident=False):
    """翻边后折叠，再翻边一次；整网格审计失败时回滚，保留操作证据。"""
    bits = np.asarray(bits)
    initial = int(invalid_faces(mesh.vertices, mesh.faces).sum())
    record = {"initial_invalid_faces": initial, "steps": [], "accepted": False}
    candidate, labels = mesh.copy(), bits.copy()
    if initial:
        for operation in (repair_degenerate, collapse_degenerate, repair_degenerate):
            # 显式保留共同来源；相邻小面处理仅在新入口的折叠阶段开启，不改标签或终态门槛。
            if operation is collapse_degenerate:
                candidate, labels, details = operation(candidate, labels, allow_shared=allow_shared,
                    allow_small_incident=allow_small_incident)
            else:
                candidate, labels, details = operation(candidate, labels, allow_shared=allow_shared)
            record["steps"].append({"operation": operation.__name__, "details": details})
            if not invalid_faces(candidate.vertices, candidate.faces).any():
                break
    valid, details = audit(candidate)
    # 原输入可能含退化面，但闭合性、绕序、分量数及欧拉特征必须保持。
    topology = (candidate.is_watertight == mesh.is_watertight and candidate.is_winding_consistent == mesh.is_winding_consistent
                and candidate.euler_number == mesh.euler_number
                and len(candidate.split(only_watertight=False)) == len(mesh.split(only_watertight=False)))
    remaining = int(invalid_faces(candidate.vertices, candidate.faces).sum())
    # 顶点与面中心双向探针补充局部平面约束；仍不声称连续距离证书。
    forward = MeshDistance(as_polydata(mesh))(np.vstack([candidate.vertices, candidate.triangles_center]))
    reverse = MeshDistance(as_polydata(candidate))(np.vstack([mesh.vertices, mesh.triangles_center]))
    distance = max(float(forward.max(initial=0)), float(reverse.max(initial=0)))
    record.update(audit=details, topology_preserved=bool(topology), remaining_invalid_faces=remaining,
                  geometry_probe_max_mm=distance, geometry_budget_mm=1e-7, continuous_geometry_certified=False,
                  accepted=bool(valid and topology and remaining == 0 and distance <= 1e-7))
    if record["accepted"]:
        return candidate, labels, record
    return mesh.copy(), bits.copy(), record
