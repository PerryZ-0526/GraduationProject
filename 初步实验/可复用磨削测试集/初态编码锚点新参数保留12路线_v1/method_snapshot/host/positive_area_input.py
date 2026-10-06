"""诊断性输入校验：分开记录真正零面积和极小正面积，不修改输出验收。"""

import numpy as np
from geometry_preservation_audit import mesh_valid


def positive_area_input(mesh):
    """仅供冻结开发诊断；拓扑、自交报警及FP32真实零面积仍拒绝。"""
    if not np.isfinite(mesh.vertices).all() or len(mesh.faces) == 0:
        return False, {"finite": False, "area_policy": "development_true_zero_input_check"}
    _, historical = mesh_valid(mesh)
    checks = dict(historical)
    checks["historical_area_threshold_counts"] = {"fp64": historical["zero_area_faces"], "fp32": historical["fp32_zero_area_faces"]}
    arithmetic = []
    for coordinates in (mesh.vertices.astype(np.float64), mesh.vertices.astype(np.float32)):
        triangles = coordinates[mesh.faces]
        area = np.linalg.norm(np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0]), axis=1) / 2
        arithmetic.append({"dtype": str(coordinates.dtype), "zero_faces": int((area == 0).sum()),
                           "nonfinite_areas": int((~np.isfinite(area)).sum()),
                           "small_positive_faces": int(((area > 0) & (area <= 1e-12)).sum()), "min_area_mm2": float(area.min())})
    checks.update(zero_area_faces=arithmetic[0]["zero_faces"], fp32_zero_area_faces=arithmetic[1]["zero_faces"],
                  area_arithmetic=arithmetic, area_policy="development_true_zero_input_check",
                  small_positive_faces_are_risk_statistics=True, output_policy_unchanged=True)
    valid = checks["finite"] and checks["watertight"] and checks["winding_consistent"] and checks["vertex_manifold_closed"] and checks["self_intersection_faces"] == 0
    valid = valid and all(a["zero_faces"] == 0 and a["nonfinite_areas"] == 0 for a in arithmetic)
    return bool(valid), checks
