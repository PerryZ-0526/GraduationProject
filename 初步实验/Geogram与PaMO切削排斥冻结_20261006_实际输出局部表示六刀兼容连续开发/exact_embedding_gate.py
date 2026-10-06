"""以绑定同一保存对象的全量精确嵌入证据判断自交，不使用报警面数截断。"""

import hashlib

from geometry_preservation_audit import mesh_valid
from positive_area_input import positive_area_input


def stored_mesh_sha256(mesh):
    """使用与17位OBJ保存完全相同的文本序列，绑定当前内存几何。"""
    digest = hashlib.sha256()
    for x, y, z in mesh.vertices:
        digest.update(f"v {x:.17g} {y:.17g} {z:.17g}\n".encode("utf8"))
    for a, b, c in mesh.faces:
        digest.update(f"f {a + 1} {b + 1} {c + 1}\n".encode("utf8"))
    return digest.hexdigest()


def mesh_valid_full_embedding_legacy(mesh, certificate):
    """保留原面积与拓扑门槛，精确证据缺失、无效或摘要不符一律拒绝。"""
    _, metrics = mesh_valid(mesh)
    bound = certificate.get("saved_mesh_sha256", certificate.get("saved_sha256")) == stored_mesh_sha256(mesh)
    embedded = bool(certificate.get("embedded_closed", False) and bound)
    metrics.update(historical_unresolved_alarm_faces=metrics["self_intersection_faces"],
                   full_exact_embedding_bound=embedded,
                   intersection_check_interpretation="同一保存FP64对象的全量CGAL EPECK嵌入证据，不以报警数量代替交叠判定")
    if embedded:
        metrics["self_intersection_faces"] = 0
    valid = all((embedded, metrics["finite"], metrics["zero_area_faces"] == 0,
                 metrics["fp32_zero_area_faces"] == 0, metrics["watertight"],
                 metrics["winding_consistent"], metrics["vertex_manifold_closed"]))
    return bool(valid), metrics


def mesh_input_valid_full_embedding(mesh, certificate):
    """输入仍采用原真零面积协议，绑定全量证据替代报警截断，不影响输出面积门槛。"""
    _, metrics = positive_area_input(mesh)
    bound = certificate.get("saved_mesh_sha256", certificate.get("saved_sha256")) == stored_mesh_sha256(mesh)
    embedded = bool(certificate.get("embedded_closed", False) and bound)
    metrics.update(historical_unresolved_alarm_faces=metrics.get("self_intersection_faces", 0),
                   full_exact_embedding_bound=embedded,
                   intersection_check_interpretation="同一保存FP64输入的完整精确嵌入证据")
    if embedded:
        metrics["self_intersection_faces"] = 0
    valid = embedded and all(metrics.get(key, False) for key in
        ("finite", "watertight", "winding_consistent", "vertex_manifold_closed"))
    valid = valid and all(a["zero_faces"] == 0 and a["nonfinite_areas"] == 0 for a in metrics.get("area_arithmetic", []))
    return bool(valid), metrics


ACTUAL_OUTPUT_REPRESENTATION_GUARD = None


def mesh_valid_full_embedding(mesh, certificate):
    """显式输出上下文要求物理及实际局部GPU表示同时有效，旧世界转换结果留作诊断。"""
    valid, metrics = mesh_valid_full_embedding_legacy(mesh, certificate)
    if ACTUAL_OUTPUT_REPRESENTATION_GUARD is None:
        return valid, metrics
    physical_valid = all((metrics["full_exact_embedding_bound"], metrics["finite"],
                          metrics["zero_area_faces"] == 0, metrics["watertight"],
                          metrics["winding_consistent"], metrics["vertex_manifold_closed"]))
    if not physical_valid:
        return False, metrics
    actual_valid, actual = ACTUAL_OUTPUT_REPRESENTATION_GUARD(mesh, certificate)
    metrics.update(legacy_world_FP32_gate_accepted=valid, actual_output_representation=actual,
                   output_representation_protocol="bound_actual_CUDA_and_Warp_at_declared_operation_origin")
    return bool(actual_valid), metrics
