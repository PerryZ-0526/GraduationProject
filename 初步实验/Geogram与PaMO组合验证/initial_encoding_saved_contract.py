"""独立重算编码退化集合并核对实际保存对象中的初态固定点。"""
import numpy as np


def check_initial_encoding_record(source_vertices, before_vertices, faces, output_vertices, ids, record):
    source_vertices = np.asarray(source_vertices, float)
    before_vertices = np.asarray(before_vertices, float)
    output_vertices = np.asarray(output_vertices, float)
    faces = np.asarray(faces, int)
    ids = np.asarray(ids, int)
    # 复审从源和投影前保存对象重算实际编码，而不相信记录中的面数量。
    if before_vertices.shape != output_vertices.shape or len(ids) != len(before_vertices):
        return dict(passed=False, reason="保存对象形状不符")
    extent = np.ptp(source_vertices, axis=0).max()
    if not np.isfinite(extent) or extent <= 0 or not np.isfinite(before_vertices).all():
        return dict(passed=False, reason="源尺度或投影前坐标无效")
    scale = 1./extent
    encoded = (before_vertices*scale-source_vertices.mean(axis=0)*scale).astype(np.float32).astype(float)
    tri = encoded[faces]
    area = np.linalg.norm(np.cross(tri[:,1]-tri[:,0], tri[:,2]-tri[:,0]), axis=1)*.5
    degenerate = area <= 1e-12*scale*scale
    affected = np.unique(faces[degenerate])
    tri = before_vertices[faces]
    physical = np.linalg.norm(np.cross(tri[:,1]-tri[:,0], tri[:,2]-tri[:,0]), axis=1)*.5
    raw_added = record.get('added_vertices', [])
    added = np.asarray(raw_added, int)
    indices_ok = bool(added.ndim == 1 and np.all(added >= 0) and np.all(added < len(ids))
        and len(np.unique(added)) == len(added) and added.tolist() == raw_added)
    allowed = bool(indices_ok and np.isin(added, affected).all() and np.all(ids[added] < 0))
    precondition = record.get('precondition', {})
    count_ok = precondition.get('encoded_degenerate_faces') == int(degenerate.sum())
    fixed_ok = bool(np.array_equal(before_vertices[affected], output_vertices[affected]))
    physical_ok = bool(np.all(physical > 1e-12))
    passed = allowed and count_ok and fixed_ok and physical_ok and precondition.get('all_degenerate_vertices_fixed') is True
    return dict(passed=bool(passed), encoded_degenerate_faces=int(degenerate.sum()),
        recorded_added_vertices_valid=allowed, all_encoded_degenerate_vertices_initial_exact=fixed_ok,
        physical_area_valid=physical_ok)
