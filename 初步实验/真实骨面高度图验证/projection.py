"""沿计划法向对真实三角骨面求全部交点，不把背面交点当成投影失败。"""
from pathlib import Path
import sys
import numpy as np
import trimesh
from rtree import index

DEMO = Path(__file__).parents[1]/'真实骨模型演示'
sys.path.insert(0, str(DEMO))
import real_bone_demo as R


class ProjectedSurface:
    """保留全部射线交点、正向层数及最外层原始三角面索引。"""
    def __init__(self, mesh):
        self.mesh = mesh
        self.triangles = mesh.triangles
        xy = self.triangles[..., :2]
        self.a = xy[:, 0]
        self.u, self.v = xy[:, 1]-self.a, xy[:, 2]-self.a
        self.det = self.u[:, 0]*self.v[:, 1]-self.u[:, 1]*self.v[:, 0]
        valid = np.flatnonzero(np.abs(self.det) > 1e-12)
        self.tree = index.Index((int(i), (*xy[i].min(axis=0), *xy[i].max(axis=0)), None) for i in valid)

    def query(self, points):
        heights = np.full(len(points), np.nan)
        faces = np.full(len(points), -1, dtype=int)
        counts = np.zeros(len(points), dtype=int)
        front_counts = np.zeros(len(points), dtype=int)
        thickness = np.full(len(points), np.nan)
        for j, (x, y) in enumerate(points):
            ids = np.array(list(self.tree.intersection((x, y, x, y))), dtype=int)
            if not len(ids):
                continue
            delta = [x, y]-self.a[ids]
            s = (delta[:, 0]*self.v[ids, 1]-delta[:, 1]*self.v[ids, 0])/self.det[ids]
            t = (self.u[ids, 0]*delta[:, 1]-self.u[ids, 1]*delta[:, 0])/self.det[ids]
            inside = (s >= -1e-10) & (t >= -1e-10) & (s+t <= 1+1e-10)
            ids, s, t = ids[inside], s[inside], t[inside]
            if not len(ids):
                continue
            tri = self.triangles[ids]
            z = tri[:, 0, 2]+s*(tri[:, 1, 2]-tri[:, 0, 2])+t*(tri[:, 2, 2]-tri[:, 0, 2])
            # 共边或共顶点重复命中按高度合并，容差只用于计数，不移动骨面。
            order = np.argsort(-z)
            unique = np.r_[True, np.abs(np.diff(z[order])) > 1e-7]
            order = order[unique]
            heights[j], faces[j] = z[order[0]], ids[order[0]]
            counts[j] = len(order)
            front_counts[j] = np.sum(self.det[ids[order]] > 0)
            if len(order) >= 2:
                thickness[j] = z[order[0]]-z[order[1]]
        return dict(z=heights, face=faces, crossings=counts, front_layers=front_counts, top_interval_mm=thickness)


def load_bone():
    """复用已记录标志点与拟合，不改变原STL或原演示的坐标约定。"""
    source = trimesh.load(R.SCAP_STL, force='mesh')
    transform, normal = R.fit_glenoid_frame(source)
    local = source.copy()
    local.apply_transform(np.linalg.inv(transform))
    return source, local, transform


if __name__ == '__main__':
    source, local, transform = load_bone()
    surface = ProjectedSurface(local)
    for radius in (4, 9, 12.5, 15):
        axis = np.arange(-radius+.031, radius, .3)
        points = np.array(np.meshgrid(axis, axis)).reshape(2, -1).T
        points = points[np.linalg.norm(points, axis=1) < radius]
        result = surface.query(points)
        valid = result['face'] >= 0
        nz = local.face_normals[result['face'][valid], 2]
        print(radius, len(points), 'missing', int(np.sum(~valid)), 'layers', np.unique(result['front_layers'], return_counts=True),
              'height', np.nanpercentile(result['z'], [0, 50, 100]), 'nz', np.percentile(nz, [0, 5, 50]), flush=True)
