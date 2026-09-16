"""已有Manifold双精度连续布尔参照；质量不足仍保留诊断序列，不作为发布成功。"""
from datetime import datetime, timezone, timedelta
from time import perf_counter
from importlib.metadata import version
import json
import numpy as np
import trimesh
import manifold3d as md
from experiment import OUT, load_candidate
from real_patch import local_trajectory
from joint import mesh_quality


def manifold(mesh):
    return md.Manifold(md.Mesh64(np.asarray(mesh.vertices, dtype=np.float64),
                                  np.asarray(mesh.faces, dtype=np.uint64)))


def quality(mesh):
    """统一中心4毫米圆盘和高度窗作为诊断ROI，不用全骨既有差面掩盖新差面。"""
    center = mesh.triangles_center
    ids = np.flatnonzero((np.linalg.norm(center[:, :2], axis=1) <= 4.) & (center[:, 2] >= -2.) & (center[:, 2] <= 3.))
    q, angles, area = mesh_quality(mesh.vertices, mesh.faces[ids])
    return dict(roi_faces=len(ids), min_q=float(q.min()), min_angle_deg=float(angles.min()),
                bad_faces=int(np.sum((q < .4) | (angles < 25) | (area <= 1e-12))),
                watertight=bool(mesh.is_watertight), winding=bool(mesh.is_winding_consistent))


if __name__ == '__main__':
    folder = OUT/datetime.now(timezone(timedelta(hours=8))).strftime('boolean_%Y%m%d_%H%M%S')
    folder.mkdir()
    candidate, chart = load_candidate()
    runs = []
    for subdivision in (2, 3):
        bone = manifold(candidate['whole'])
        assert bone.status() == md.Error.NoError
        sphere = trimesh.creation.icosphere(subdivisions=subdivision, radius=3.)
        inner_radius = np.einsum('ij,ij->i', sphere.face_normals, sphere.triangles[:, 0]).min()
        rows = []
        for step, tool in enumerate(local_trajectory(1.8), 1):
            started = perf_counter()
            a, b = np.array([*tool.start, tool.z]), np.array([*tool.end, tool.z])
            capsule = trimesh.convex.convex_hull(np.vstack([sphere.vertices+a, sphere.vertices+b]))
            cutter = manifold(capsule)
            bone = bone-cutter
            data = bone.to_mesh64()
            mesh = trimesh.Trimesh(data.vert_properties[:, :3], data.tri_verts, process=False)
            compute_ms = (perf_counter()-started)*1000
            row = dict(step=step, compute_ms=compute_ms, status=str(bone.status()), **quality(mesh))
            row['compute_and_quality_ms'] = (perf_counter()-started)*1000
            rows.append(row)
            np.savez_compressed(folder/f's{subdivision}_{step}.npz', vertices=mesh.vertices, faces=mesh.faces)
        runs.append(dict(subdivision=subdivision, sphere_faces=len(sphere.faces),
            capsule_hausdorff_bound_mm=float(3.-inner_radius), initial=quality(candidate['whole']), records=rows))
        (folder/'results.json').write_text(json.dumps(dict(time_bjt=folder.name, manifold_version=version('manifold3d'),
            target_z=1.8, runs=runs), ensure_ascii=False, indent=2), encoding='utf-8')
    print(folder)
