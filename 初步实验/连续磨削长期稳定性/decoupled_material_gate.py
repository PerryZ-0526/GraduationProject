"""解耦分支材料保存对象的基本有效性门控，不把质量维护结果用于下一刀。"""
import hashlib
import json
from pathlib import Path
import subprocess
import numpy as np
import trimesh
from audit_pose_full_embedding import obj_bytes, vertex_manifold_closed


def audit_material(path, folder, executable):
    """只证明保存网格基本有效；累计参照和连续几何误差另行报告。"""
    path, folder, executable = Path(path), Path(folder), Path(executable)
    folder.mkdir(parents=True, exist_ok=False)
    mesh = trimesh.load(path, force='mesh', process=False)
    vertices, faces = np.asarray(mesh.vertices), np.asarray(mesh.faces)
    areas = mesh.area_faces
    local = bool(len(faces) and np.isfinite(vertices).all() and np.isfinite(areas).all()
                 and np.all(areas > 1e-12) and mesh.is_watertight and mesh.is_winding_consistent
                 and vertex_manifold_closed(faces))
    # 仅删除加载器未引用的顶点索引，不移动保存坐标；以实际重编码对象绑定精确证书。
    canonical = folder/'saved_material.obj'
    canonical.write_bytes(obj_bytes(vertices, faces))
    run = subprocess.run([str(executable), str(canonical)], capture_output=True, text=True)
    certificate = json.loads(run.stdout) if run.returncode == 0 and run.stdout.strip() else {}
    exact = bool(run.returncode == 0 and certificate.get('embedded_closed')
                 and certificate.get('vertices') == len(vertices) and certificate.get('faces') == len(faces))
    return {'passed': local and exact, 'source_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'canonical_sha256': hashlib.sha256(canonical.read_bytes()).hexdigest(),
            'checker_sha256': hashlib.sha256(executable.read_bytes()).hexdigest(),
            'local_mesh_valid': local, 'exact_result': certificate,
            'returncode': run.returncode, 'stdout': run.stdout, 'stderr': run.stderr,
            'cumulative_material_geometry_certificate': None,
            'scope': '保存FP64基本材料门控；不是累计材料正确性或连续误差证书'}
