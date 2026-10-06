"""旧八位清理产生重复面时，只补严格同坐标焊接，不舍入、抵消或删面。"""
import numpy as np
import trimesh
from run_canonical_stepwise_feedback import canonical_cleanup
from canonical_clean_source import canonical_clean_source


def clean_with_exact_duplicate_fallback(mesh, bits, allow_shared=False):
    try:
        return canonical_cleanup(mesh, bits, allow_shared=allow_shared)
    except ValueError as error:
        if str(error) != '去重产生重复面，来源或绕序可能冲突，停止清理':
            raise
        original_error = str(error)
    bits = np.asarray(bits)
    if len(bits) != len(mesh.faces) or not np.isfinite(mesh.vertices).all():
        raise ValueError('严格焊接源非有限或来源长度不同')
    # 完全相同的浮点坐标才合并，三顶点不同的面一张也不删除。
    vertices, inverse = np.unique(np.asarray(mesh.vertices, np.float64), axis=0, return_inverse=True)
    faces = inverse[mesh.faces]
    if np.any(np.diff(np.sort(faces, axis=1), axis=1) == 0):
        raise ValueError('严格焊接仍有重复顶点退化面，保留拒绝')
    if len(np.unique(np.sort(faces, axis=1), axis=0)) != len(faces):
        raise ValueError('严格焊接仍有重复面，保留拒绝')
    result, labels, ordering = canonical_clean_source(trimesh.Trimesh(vertices, faces, process=False), bits)
    return result, labels, {'role': 'exact_coordinate_weld_after_rounded_duplicate_failure',
        'original_cleanup_error': original_error, 'coordinates_changed': False, 'faces_removed': 0,
        'input_vertices': len(mesh.vertices), 'output_vertices': len(result.vertices),
        'input_faces': len(mesh.faces), 'output_faces': len(result.faces), 'canonical_order': ordering,
        'full_physical_and_actual_encoding_gates_still_required': True}
