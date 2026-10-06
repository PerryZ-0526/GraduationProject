"""同一保存材料场的提取精度隔离对照；保留退化面，不自动修补。"""
import argparse
import json
from pathlib import Path
import numpy as np
import pyvista as pv
import vtk
from timed_paths import beijing_now, digest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--field', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    data = np.load(args.field)
    field, axis = data['field'], data['axis_mm']
    spacing = float(axis[1] - axis[0])
    image = pv.ImageData(dimensions=field.shape, spacing=(spacing,) * 3, origin=(float(axis[0]),) * 3)
    image.point_data['material'] = field.ravel(order='F')
    rows = []
    for name, precision in (('default', vtk.vtkAlgorithm.DEFAULT_PRECISION),
                            ('double', vtk.vtkAlgorithm.DOUBLE_PRECISION)):
        contour = vtk.vtkContourFilter()
        contour.SetInputData(image)
        contour.SetValue(0, 0)
        contour.SetOutputPointsPrecision(precision)
        contour.Update()
        mesh = pv.wrap(contour.GetOutput()).triangulate()
        path = args.output / f'{name}.vtp'
        mesh.save(path)
        triangles = mesh.points.astype(np.float64)[mesh.faces.reshape(-1, 4)[:, 1:]]
        areas = np.linalg.norm(np.cross(triangles[:, 1] - triangles[:, 0],
                                        triangles[:, 2] - triangles[:, 0]), axis=1) / 2
        rows.append({'method': name, 'actual_coordinate_dtype': str(mesh.points.dtype),
                     'faces': mesh.n_cells, 'open_edges': mesh.n_open_edges,
                     'exact_zero_area_faces': int(np.count_nonzero(areas == 0)),
                     'area_at_most_1e_12_mm2_faces': int(np.count_nonzero(areas <= 1e-12)),
                     'duplicate_coordinate_vertices': mesh.n_points - len(np.unique(mesh.points, axis=0)),
                     'sha256': digest(path)})
    result = {'created_at_beijing': beijing_now(), 'field_sha256': digest(args.field),
              'zero_field_nodes': int(np.count_nonzero(field == 0)),
              'script_sha256': digest(__file__), 'rows': rows,
              'scope': '精度隔离，未删面、未移动顶点、未执行精确自交或完整反馈'}
    (args.output / '01-同材料提取精度对照.json').write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
