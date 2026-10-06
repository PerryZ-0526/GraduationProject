"""原固定几何后端的纯坐标前提，避免GPU进程导入本机几何审计依赖。"""
import numpy as np


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
