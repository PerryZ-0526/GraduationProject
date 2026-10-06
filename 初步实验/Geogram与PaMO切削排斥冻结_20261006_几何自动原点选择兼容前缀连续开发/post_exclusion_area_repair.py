"""已通过整面排斥但仍有数值面积风险时，补局部折叠并重新认证。"""
import numpy as np
from incident_plane_collapse import collapse_degenerate
from cut_exclusion import supporting_planes, face_separators, certify_face_support
from exact_embedding_gate import mesh_valid_full_embedding


def repair_post_exclusion_area(mesh, tools, side):
    planes = [supporting_planes(tool) for tool in tools]
    def certificates(candidate):
        return [certify_face_support(candidate, n, d, face_separators(candidate, tool)[0]) for tool, (n, d) in zip(tools, planes)]
    def guard(candidate, _operation_regions):
        # 每次折叠都须保持全部累计工具整面排斥，操作域标记不是原始面来源。
        return all(c['passed'] for c in certificates(candidate))
    candidate, _, collapse = collapse_degenerate(mesh, np.ones(len(mesh.faces), dtype=int), allow_small_incident=True, candidate_guard=guard)
    classification = side.classify(candidate, [candidate.vertices.mean(axis=0)])
    valid, metrics = mesh_valid_full_embedding(candidate, classification)
    anchors = [side.anchor(candidate, tool, n, d) for tool, (n, d) in zip(tools, planes)]
    proofs = certificates(candidate)
    topology = candidate.euler_number == mesh.euler_number and len(candidate.split(only_watertight=False)) == len(mesh.split(only_watertight=False))
    accepted = bool(valid and topology and all(p['passed'] for p in proofs) and all(a['passed'] for a in anchors))
    return candidate if accepted else mesh, {'accepted': accepted, 'metrics': metrics, 'collapse': collapse,
        'same_topology': topology, 'face_support_certificate': proofs, 'outside_anchor_certificate': anchors,
        'operation_regions_role': '单一输出操作域，不是输入来源标签', 'actual_GPU_calls': 0,
        'continuous_target_distance_certified': False, 'movement_CCD_certified': False}
