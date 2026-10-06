"""仅对去重形成的同来源反向面成对抵消，完整拓扑和几何检查后返回。"""
import numpy as np
import trimesh
from scipy.spatial import cKDTree
from locality_cleanup import clean_provenance
from exact_alarm_contact import mesh_valid_exact_contacts


def opposed_pairs(faces,bits):
    """每个重复组必须恰为两个同来源反向面；同向、混合来源或多重面拒绝。"""
    keys=np.sort(faces,axis=1)
    _,inverse,counts=np.unique(keys,axis=0,return_inverse=True,return_counts=True)
    pairs=[]
    for group in np.flatnonzero(counts>1):
        ids=np.flatnonzero(inverse==group)
        if len(ids)!=2 or bits[ids[0]]!=bits[ids[1]]:
            raise ValueError("成对抵消要求恰好两个同来源面")
        first,second=faces[ids]
        if any(np.array_equal(np.roll(first,n),second) for n in range(3)):
            raise ValueError("同向重复面不能按反向链抵消")
        pairs.append(ids.tolist())
    return pairs


def clean_cancel_opposed(mesh,bits,allow_shared=False):
    """旧清理成功时原样返回；重复面负例只尝试明确的反向链抵消。"""
    try:
        return clean_provenance(mesh,bits,allow_shared=allow_shared)
    except ValueError as error:
        if str(error)!="去重产生重复面，来源或绕序可能冲突，停止清理":
            raise
    bits=np.asarray(bits)
    candidate=trimesh.Trimesh(vertices=mesh.vertices.copy(),faces=mesh.faces.copy(),process=False)
    candidate.merge_vertices(digits_vertex=8)
    faces=candidate.faces
    keep=(faces[:,0]!=faces[:,1])&(faces[:,1]!=faces[:,2])&(faces[:,2]!=faces[:,0])
    surviving=np.flatnonzero(keep)
    pairs=opposed_pairs(faces[keep],bits[keep])
    if not pairs:
        raise ValueError("未找到可抵消反向面")
    cancelled=[int(surviving[index]) for pair in pairs for index in pair]
    keep[cancelled]=False
    candidate.update_faces(keep)
    candidate.remove_unreferenced_vertices()
    # 在更细的坐标键上核对原实体拓扑；原始OBJ可能使用同坐标但不同索引。
    baseline=mesh.copy()
    baseline.merge_vertices(digits_vertex=16)
    # 细精度键也可能产生重复顶点面，仅移除这类索引已坍缩的面，与旧清理规则一致。
    base_faces=baseline.faces
    base_keep=(base_faces[:,0]!=base_faces[:,1])&(base_faces[:,1]!=base_faces[:,2])&(base_faces[:,2]!=base_faces[:,0])
    baseline.update_faces(base_keep)
    baseline.remove_unreferenced_vertices()
    valid,metrics=mesh_valid_exact_contacts(candidate)
    baseline_closed=bool(baseline.is_watertight and baseline.is_winding_consistent)
    topology=bool(baseline_closed and candidate.euler_number==baseline.euler_number and
        len(candidate.split(only_watertight=False))==len(baseline.split(only_watertight=False)))
    if not valid or metrics["fp32_zero_area_faces"] or not topology:
        raise ValueError("反向面抵消后全网格或原实体拓扑不通过")
    displacement=float(cKDTree(candidate.vertices).query(mesh.vertices)[0].max())
    # 成对抵消有不同于顶点焊接的覆盖风险，须另作完整顶点和面积距离探针。
    from run_constrained_feedback import global_geometry
    geometry=global_geometry(candidate,mesh)
    if displacement>1e-7 or geometry["probe_max_mm"]>1e-7:
        raise ValueError("反向面抵消超出原表面1e-7毫米探针预算")
    return candidate,bits[keep],{"digits_vertex":8,"cancelled_opposed_original_face_pairs":
        [[int(surviving[index]) for index in pair] for pair in pairs],
        "removed_collapsed_faces":int(len(mesh.faces)-len(surviving)),
        "max_raw_vertex_to_clean_vertex_mm":displacement,"surviving_original_face_ids":np.flatnonzero(keep).tolist(),
        "baseline_topology_digits":16,"baseline_removed_collapsed_faces":int((~base_keep).sum()),
        "topology_preserved":topology,"validated_metrics":metrics,
        "raw_to_clean_geometry":geometry,"scope":"同来源反向链抵消与整网格重审；非连续距离或精确CSG保证"}
