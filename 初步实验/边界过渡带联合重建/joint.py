"""按质量反馈扩展原面维护域，按几何误差补充内部采样；不放宽验收阈值。"""
from pathlib import Path
import sys
import numpy as np

sys.path.insert(0, str(Path(__file__).parents[1]/'真实骨面共边拼接'))
from stitch import (boundary_of, stitch_candidate, audit_candidate, BoneChart, Rejected,
                    ProjectedSurface, load_bone, verify_chart, mesh_quality)
from surface_patch import clip_polygon, polygon_area, triangle_height
from intersections import resolve_flags


class DomainChart(BoneChart):
    """查询越界只允许1e-10 mm内的边界舍入，返回最近边界高度而非外推平面。"""
    def __init__(self, surface, polygons):
        super().__init__(surface, polygons)
        self.edges = surface.mesh.vertices[boundary_of(surface.mesh.faces[self.ids])]

    def height(self, xy):
        shape = xy.shape[:-1]
        points = np.asarray(xy).reshape(-1, 2)
        ids = self.finder(points[:, 0], points[:, 1])
        values = np.empty(len(points))
        valid = ids >= 0
        values[valid] = np.sum(self.gradient[ids[valid]]*points[valid], axis=1)+self.intercept[ids[valid]]
        a, delta = self.edges[:, 0, :2], self.edges[:, 1, :2]-self.edges[:, 0, :2]
        for i in np.flatnonzero(~valid):
            t = np.clip(np.sum((points[i]-a)*delta, axis=1)/np.sum(delta**2, axis=1), 0., 1.)
            distance = np.linalg.norm(points[i]-a-t[:, None]*delta, axis=1)
            edge = int(distance.argmin())
            if distance[edge] > 1e-10:
                raise Rejected('查询超出原始图域及显式数值边界容差')
            values[i] = self.edges[edge, 0, 2]+t[edge]*(self.edges[edge, 1, 2]-self.edges[edge, 0, 2])
        return values.reshape(shape)


def verified_domain(surface, removed):
    """验证原始三角盘的单值可见性，不把扩展到方形外等同于外推。"""
    boundary_of(surface.mesh.faces[removed])
    selected = set(map(int, removed))
    polygons = {}
    for i in removed:
        triangle = surface.triangles[i]
        if triangle[:, 2].min() < -2 or triangle[:, 2].max() > 3 or surface.mesh.face_normals[i, 2] < .5:
            raise Rejected('扩展域超过原面高度窗或坡度限制')
        polygon = triangle[:, :2]
        polygons[int(i)] = polygon
        for j in surface.tree.intersection((*polygon.min(0), *polygon.max(0))):
            if j == i:
                continue
            other = surface.triangles[j, :, :2]
            if surface.det[j] < 0:
                other = other[::-1]
            overlap = clip_polygon(polygon, other)
            if polygon_area(overlap) <= 1e-9:
                continue
            if j in selected:
                raise Rejected('扩展域原始面存在投影重叠')
            if np.max(triangle_height(surface.triangles[j], overlap)-triangle_height(triangle, overlap)) > 1e-6:
                raise Rejected('扩展域被其他原始骨面遮挡')
    return DomainChart(surface, polygons)


def solve(surface, removed, area=.0125, expand=True, refine=True, limit=16):
    """单调扩展原面集合；有限预算内无合格候选则明确失败，不发布中间状态。"""
    removed = np.asarray(removed).copy()
    points = np.empty((0, 2))
    history = []
    candidate = chart = None
    built_removed = removed.copy()
    for iteration in range(limit):
        chart = verified_domain(surface, removed)
        built_removed = removed.copy()
        candidate = stitch_candidate(surface.mesh, removed, chart, area, True, points)
        audit, errors, angles = audit_candidate(surface, candidate)
        resolve_flags(candidate, audit)
        audit.update(iteration=iteration, removed_faces=len(removed), extra_points=len(points))
        history.append(audit)
        print(iteration, len(removed), audit['min_angle_deg'], audit['error_max_mm'],
              audit['self_intersection_flags'], flush=True)
        if audit['accepted']:
            break
        q, _, _ = mesh_quality(candidate['vertices'], candidate['faces'])
        bad = (q < .4) | (angles < 25)
        bad_vertices = np.unique(candidate['faces'][bad])
        boundary_vertices = bad_vertices[bad_vertices < len(candidate['source_ids'])]
        changed = False
        if expand and len(boundary_vertices):
            original_ids = candidate['source_ids'][boundary_vertices]
            neighbors = np.flatnonzero(np.any(np.isin(surface.mesh.faces, original_ids), axis=1))
            grown = np.union1d(removed, neighbors)
            if len(grown) > len(removed):
                removed, changed = grown, True
        if refine and np.any(errors > .08):
            # 0.08是生成目标留裕量，最终验收始终为0.1；每个超差面统一插入重心。
            added = candidate['vertices'][candidate['faces'][errors > .08], :2].mean(axis=1)
            points = np.unique(np.vstack([points, added]), axis=0)
            changed = True
        if not changed:
            break
    return candidate, chart, history, built_removed


if __name__ == '__main__':
    _, source, _ = load_bone()
    surface = ProjectedSurface(source)
    _, polygons = verify_chart(surface, 8.)
    removed = np.array([i for i in polygons if np.max(np.abs(source.triangles[i, :, :2])) < 8.])
    candidate, chart, history, removed = solve(surface, removed)
    print(history[-1])
