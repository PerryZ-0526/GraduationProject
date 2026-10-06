"""退化输入先作有限局部修复，由完整精确检查决定是否接受。"""
from pathlib import Path
from time import perf_counter
import numpy as np
import trimesh
from event_store import atomic_json, file_identity, now


def repair_before_reject(mesh, bits, validate, folder):
    from physical_repair_operations import invalid_faces, repair_degenerate, collapse_degenerate
    from geometry_preservation_audit import MeshDistance
    from audit_pamo_outputs import as_polydata
    from locality_masks import save_obj_fp64
    started = perf_counter()
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=False)
    labels = np.asarray(bits).copy()
    initial_bad = int(np.count_nonzero(mesh.area_faces <= 1e-12))
    record = {'version': 'local_degenerate_repair_exact_embedding_v1', 'time_beijing': now(),
              'initial_invalid_faces': initial_bad, 'steps': [], 'accepted': False,
              'repair_geometry_budget_mm': 1e-7, 'geometry_policy': '沿用局部清理预算，累计反馈距离仅统计'}
    candidate = mesh.copy()
    if initial_bad and np.isfinite(mesh.vertices).all():
        # 沿用已有三个有限操作与来源保护，只将最终裁决交给完整检查器。
        for operation in (repair_degenerate, collapse_degenerate, repair_degenerate):
            if operation is collapse_degenerate:
                candidate, labels, detail = operation(candidate, labels, allow_shared=True, allow_small_incident=True)
            else:
                candidate, labels, detail = operation(candidate, labels, allow_shared=True)
            record['steps'].append({'operation': operation.__name__, 'details': detail})
            if not invalid_faces(candidate.vertices, candidate.faces).any():
                break
    destination = folder / 'repaired_source.obj'
    save_obj_fp64(candidate, destination)
    # 所有检查绑定重新读取的保存对象，避免内存对象与实际GPU输入不同。
    saved = trimesh.load(destination, force='mesh', process=False)
    topology = bool(saved.is_watertight == mesh.is_watertight and saved.is_winding_consistent == mesh.is_winding_consistent
        and saved.euler_number == mesh.euler_number
        and len(trimesh.graph.connected_components(saved.face_adjacency, nodes=np.arange(len(saved.faces)), engine='scipy'))
            == len(trimesh.graph.connected_components(mesh.face_adjacency, nodes=np.arange(len(mesh.faces)), engine='scipy')))
    forward = MeshDistance(as_polydata(mesh))(np.vstack((saved.vertices, saved.triangles_center)))
    reverse = MeshDistance(as_polydata(saved))(np.vstack((mesh.vertices, mesh.triangles_center)))
    distance = max(float(forward.max(initial=0)), float(reverse.max(initial=0)))
    remaining = int(np.count_nonzero(saved.area_faces <= 1e-12))
    valid, metrics = validate(saved, folder / 'full_geometry_checks', 'repaired_input')
    accepted = bool(initial_bad and remaining == 0 and topology and valid and distance <= 1e-7
                    and len(labels) == len(saved.faces))
    record.update(accepted=accepted, remaining_invalid_faces=remaining, topology_preserved=topology,
        vertices_exact=bool(np.array_equal(saved.vertices, mesh.vertices)), geometry_probe_max_mm=distance,
        continuous_geometry_certified=False, saved_mesh=file_identity(destination), validated_metrics=metrics,
        cleanup_wall_ms=(perf_counter() - started) * 1000)
    atomic_json(folder / 'repaired_labels.json', {'operand_bits': labels.tolist()})
    atomic_json(folder / '01-局部退化清理与完整复审.json', record)
    return (saved, labels, record) if accepted else (mesh, np.asarray(bits), record)
