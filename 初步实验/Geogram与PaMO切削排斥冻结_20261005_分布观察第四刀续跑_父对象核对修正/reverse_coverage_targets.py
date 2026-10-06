"""为漏覆盖参照点匹配现有顶点，局部法向不反转，终态仍须完整审计。"""

import numpy as np
import trimesh
from vtkmodules.vtkCommonDataModel import vtkStaticCellLocator
from vtkmodules.vtkCommonCore import reference as vtk_reference

from run_constrained_feedback import as_polydata


def restore_reverse_coverage_targets(mesh, target, tolerance=.025):
    locator = vtkStaticCellLocator()
    locator.SetDataSet(as_polydata(mesh))
    locator.BuildLocator()
    nearest, cell, sub, square = [0., 0., 0.], vtk_reference(0), vtk_reference(0), vtk_reference(0.)
    selected = {}
    maximum, uncovered = 0., 0
    for index, point in enumerate(target.vertices):
        locator.FindClosestPoint(point, nearest, cell, sub, square)
        distance = float(square) ** .5
        maximum = max(maximum, distance)
        if distance <= tolerance:
            continue
        uncovered += 1
        face = mesh.faces[int(cell)]
        vertex = int(face[np.argmin(np.linalg.norm(mesh.vertices[face] - point, axis=1))])
        if vertex not in selected or distance > selected[vertex][0]:
            selected[vertex] = (distance, index)
    vertices = mesh.vertices.copy()
    owners = mesh.vertex_faces
    accepted, rejected, maximum_move = [], 0, 0.
    for vertex, (distance, index) in sorted(selected.items(), key=lambda item: (-item[1][0], item[0])):
        incident = owners[vertex]
        incident = incident[incident >= 0]
        faces = mesh.faces[incident]
        before = vertices[faces]
        after = before.copy()
        after[faces == vertex] = target.vertices[index]
        old_normals = np.cross(before[:, 1] - before[:, 0], before[:, 2] - before[:, 0])
        new_normals = np.cross(after[:, 1] - after[:, 0], after[:, 2] - after[:, 0])
        # 该浮点检查仅筛掉局部反转提案，不代替后续完整精确嵌入、面积或距离证据。
        if np.any(np.einsum("ij,ij->i", old_normals, new_normals) <= 0):
            rejected += 1
            continue
        move = float(np.linalg.norm(vertices[vertex] - target.vertices[index]))
        vertices[vertex] = target.vertices[index]
        maximum_move = max(maximum_move, move)
        accepted.append({"candidate_vertex": vertex, "reference_vertex": index, "reverse_distance_mm": distance, "movement_mm": move})
    record = {"trigger_mm": tolerance, "reference_vertices": len(target.vertices),
              "reverse_vertex_max_mm": maximum, "uncovered_reference_vertices": uncovered,
              "relocated_vertices": len(accepted), "rejected_orientation_proposals": rejected,
              "maximum_relocation_mm": maximum_move, "selected": accepted,
              "continuous_distance_certified": False, "movement_CCD_certified": False}
    return trimesh.Trimesh(vertices, mesh.faces.copy(), process=False), record
