"""对参照未被候选覆盖的顶点，按最近候选面插入最远覆盖种子。"""

import numpy as np
import trimesh
from vtkmodules.vtkCommonDataModel import vtkStaticCellLocator
from vtkmodules.vtkCommonCore import reference as vtk_reference

from run_constrained_feedback import as_polydata


def insert_reverse_coverage_seeds(mesh, target, tolerance=.025):
    """每个面至多一个种子，原边保持；完整几何及嵌入是否合法由后续门槛判断。"""
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
        face = int(cell)
        if face not in selected or distance > selected[face][0]:
            selected[face] = (distance, index)
    record = {"trigger_mm": tolerance, "reference_vertices": len(target.vertices),
              "reverse_vertex_max_mm": maximum, "uncovered_reference_vertices": uncovered,
              "inserted_vertices": len(selected), "selected": [],
              "continuous_distance_certified": False}
    if not selected:
        return mesh.copy(), record
    vertices = mesh.vertices.tolist()
    faces = []
    for face, (a, b, c) in enumerate(mesh.faces):
        if face not in selected:
            faces.append([a, b, c])
            continue
        distance, index = selected[face]
        vertex = len(vertices)
        vertices.append(target.vertices[index].tolist())
        faces.extend([[a, b, vertex], [b, c, vertex], [c, a, vertex]])
        record["selected"].append({"candidate_face": face, "reference_vertex": index, "distance_mm": distance})
    return trimesh.Trimesh(np.asarray(vertices), np.asarray(faces), process=False), record
