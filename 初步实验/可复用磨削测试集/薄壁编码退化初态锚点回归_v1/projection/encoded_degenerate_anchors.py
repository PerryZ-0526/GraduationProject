"""对物理有效、仅GPU编码退化的面绑定投影初态锚点。"""
import numpy as np
from preserved_geometry_precondition import require_fixed_degenerate_faces


def initial_encoding_anchors(vertices, faces, fixed, scale, translation):
    vertices = np.asarray(vertices, float)
    faces = np.asarray(faces, int)
    fixed = np.asarray(fixed, bool).copy()
    triangles = vertices[faces]
    physical_area = np.linalg.norm(np.cross(triangles[:, 1]-triangles[:, 0], triangles[:, 2]-triangles[:, 0]), axis=1)*.5
    # 物理无效面不能通过固定掩码绕过原面积要求。
    if not np.isfinite(vertices).all() or np.any(physical_area <= 1e-12):
        raise ValueError("初态编码锚点不能覆盖物理退化或非有限面")
    encoded = (vertices*scale+translation).astype(np.float32).astype(float)
    if not np.isfinite(encoded).all():
        raise ValueError("GPU编码坐标非有限")
    triangles = encoded[faces]
    area = np.linalg.norm(np.cross(triangles[:, 1]-triangles[:, 0], triangles[:, 2]-triangles[:, 0]), axis=1)*.5
    affected = np.unique(faces[area <= 1e-12*scale*scale])
    added = affected[~fixed[affected]]
    fixed[affected] = True
    # 原前提再次核查；不改变顶点坐标或删除接触。
    precondition = require_fixed_degenerate_faces(vertices, faces, fixed, scale, translation)
    return fixed, dict(added_vertices=added.tolist(), precondition=precondition,
        policy="投影开始前绑定物理有效而编码退化的全部面顶点；FP64初态逐位保持")
