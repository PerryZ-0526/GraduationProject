"""同一材料场的FP64提取与零值表示处理；不修改权威材料场。"""
import numpy as np
import pyvista as pv
import vtk


def extract(field, axis, structured, canonical_zero):
    field = np.asarray(field, dtype=np.float64)
    axis = np.asarray(axis, dtype=np.float64)
    spacing = float(axis[1] - axis[0])
    grid = pv.ImageData(dimensions=field.shape, spacing=(spacing,) * 3,
                        origin=(float(axis[0]),) * 3)
    if structured:
        # 显式坐标结构网格让VTK实际输出FP64；ImageData路径会忽略该精度选项。
        grid = grid.cast_to_structured_grid()
    conditioned = field.copy()
    tolerance = 32 * np.finfo(np.float64).eps * max(float(np.max(np.abs(axis))), 1)
    if canonical_zero:
        conditioned[np.abs(conditioned) <= tolerance] = 0
    grid.point_data['material'] = conditioned.ravel(order='F')
    contour = vtk.vtkContourFilter()
    contour.SetInputData(grid)
    contour.SetValue(0, 0)
    contour.SetOutputPointsPrecision(vtk.vtkAlgorithm.DOUBLE_PRECISION)
    contour.Update()
    mesh = pv.wrap(contour.GetOutput()).triangulate()
    # 该固定系数是开发表示策略，未证明为严格前向误差界或Hausdorff上界。
    info = {'structured_coordinates': structured, 'canonical_zero': canonical_zero,
            'actual_coordinate_dtype': str(mesh.points.dtype),
            'zero_tolerance_field_units': tolerance,
            'changed_field_nodes': int(np.count_nonzero(conditioned != field)),
            'changed_negative_node_classifications': int(np.count_nonzero((conditioned < 0) != (field < 0))),
            'max_field_change': float(np.max(np.abs(conditioned - field))),
            'material_state_mutated': False, 'faces_deleted': False}
    return mesh, info
