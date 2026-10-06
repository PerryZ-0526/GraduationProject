"""原固定几何后端的输入修复候选，不启用正式发布或跳过全量嵌入检查。"""
import numpy as np
from physical_repair_operations import invalid_faces,repair_degenerate,collapse_degenerate
from exact_alarm_contact import mesh_valid_exact_contacts
from geometry_preservation_audit import MeshDistance
from audit_pamo_outputs import as_polydata


def repair_preserved_input(mesh,bits):
    candidate, labels = mesh.copy(),np.asarray(bits).copy()
    initial = int(invalid_faces(candidate.vertices,candidate.faces).sum())
    record = dict(initial_arithmetic_invalid_faces=initial,steps=[],accepted_for_fixed_geometry_backend=False,
        requires_full_embedding_before_gpu=True,published=False,
        policy="仅按FP64物理面积修复；FP32退化数量保留，须交原固定几何后端验证相关顶点全部固定")
    if initial:
        for operation in (repair_degenerate,collapse_degenerate,repair_degenerate):
            if operation is collapse_degenerate:
                candidate,labels,details = operation(candidate,labels,allow_shared=True,allow_small_incident=True)
            else:
                candidate,labels,details = operation(candidate,labels,allow_shared=True)
            record["steps"].append(dict(operation=operation.__name__,details=details))
            if not invalid_faces(candidate.vertices,candidate.faces).any():
                break
    # 几何合法性仍检查保存FP64面积、连接、绕序和报警，不把FP32编码等同于物理表面。
    valid,metrics = mesh_valid_exact_contacts(candidate)
    topology = (candidate.is_watertight == mesh.is_watertight
        and candidate.is_winding_consistent == mesh.is_winding_consistent
        and candidate.euler_number == mesh.euler_number
        and len(candidate.split(only_watertight=False)) == len(mesh.split(only_watertight=False)))
    forward = MeshDistance(as_polydata(mesh))(np.vstack([candidate.vertices,candidate.triangles_center]))
    reverse = MeshDistance(as_polydata(candidate))(np.vstack([mesh.vertices,mesh.triangles_center]))
    distance = max(float(forward.max(initial=0)),float(reverse.max(initial=0)))
    fp64_bad = int(np.count_nonzero(candidate.area_faces <= 1e-12))
    fp32_triangles = candidate.vertices.astype(np.float32).astype(float)[candidate.faces]
    fp32_area = np.linalg.norm(np.cross(fp32_triangles[:,1]-fp32_triangles[:,0],
                                      fp32_triangles[:,2]-fp32_triangles[:,0]),axis=1)*.5
    # 该函数仅生成待后端绑定及精确嵌入审计的候选，旧完整流程仍使用旧修复函数。
    eligible = bool(valid and fp64_bad == 0 and topology and distance <= 1e-7)
    record.update(audit=metrics,topology_preserved=bool(topology),geometry_probe_max_mm=distance,
        geometry_budget_mm=1e-7,remaining_arithmetic_invalid_faces=int(invalid_faces(candidate.vertices,candidate.faces).sum()),
        remaining_fp64_threshold_faces=fp64_bad,remaining_fp32_true_zero_faces=int(np.count_nonzero(fp32_area == 0)),
        accepted_for_fixed_geometry_backend=eligible,continuous_geometry_certified=False)
    return (candidate,labels,record) if eligible else (mesh.copy(),np.asarray(bits).copy(),record)


def require_fixed_degenerate_faces(vertices,faces,fixed,scale,translation):
    """GPU编码退化面若含自由点必须拒绝；原固定几何只覆盖固定接触。"""
    encoded = (np.asarray(vertices)*scale+translation).astype(np.float32).astype(float)
    if not np.isfinite(encoded).all():
        raise ValueError("GPU编码坐标非有限，原固定几何分支不能覆盖")
    triangles = encoded[np.asarray(faces)]
    area = np.linalg.norm(np.cross(triangles[:,1]-triangles[:,0],triangles[:,2]-triangles[:,0]),axis=1)*.5
    degenerate = area <= 1e-12*scale*scale
    unsupported = degenerate & ~np.all(np.asarray(fixed,bool)[faces],axis=1)
    if np.any(unsupported):
        raise ValueError("GPU编码退化面仍含自由顶点，原固定几何分支不能覆盖")
    return dict(encoded_degenerate_faces=int(degenerate.sum()),all_degenerate_vertices_fixed=True)
