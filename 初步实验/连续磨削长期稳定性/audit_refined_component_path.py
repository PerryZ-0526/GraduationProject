"""细化负例小闭壳的同源连续材料通道核查。"""
import argparse
from fractions import Fraction
import json
from pathlib import Path
import numpy as np
import pyvista as pv
import trimesh
from audit_material_component_paths import rational_point, box_path_margin, segment_distance_squared
from audit_component_exact_membership import exact_inside
from timed_paths import beijing_now, digest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--evaluation', type=Path, required=True)
    parser.add_argument('--refinement', type=Path, required=True)
    args = parser.parse_args()
    output = args.refinement / '03-细化小闭壳材料通道核查.json'
    if output.exists():
        raise ValueError('核查文件禁止覆盖')
    plan = json.loads((args.evaluation / '路线00/01-实际执行输入与方法绑定.json').read_text(encoding='utf-8'))
    asset = np.load(plan['asset'])
    knots = asset['knots_mm'][asset['knot_times_s'] <= asset['times_s'][400]]
    segments = [(rational_point(a), rational_point(b)) for a, b in zip(knots[:-1], knots[1:])]
    local = np.array([(x, y, z) for x in (-2.1, 0, 2.1) for y in (-1.7, 0, 1.7) for z in (-.15, 0, .15)])
    anchors = local @ np.linalg.inv(asset['rotation']) + asset['shift_mm']
    file = args.refinement / '作者解析源网格_240.vtp'
    poly = pv.read(file)
    vertices, faces = np.asarray(poly.points), poly.faces.reshape(-1, 4)[:, 1:]
    mesh = trimesh.Trimesh(vertices, faces, process=False)
    components = trimesh.graph.connected_components(mesh.face_adjacency, nodes=np.arange(len(faces)))
    rows = []
    for component in components:
        if len(component) > 100:
            continue
        center = vertices[np.unique(faces[component])].mean(axis=0)
        center_check = exact_inside(center, vertices, faces[component])
        witnesses = []
        for anchor in anchors:
            start, end = rational_point(center), rational_point(anchor)
            margin = box_path_margin(start, end, asset['rotation'], asset['shift_mm'], 'thin_wall')
            if margin <= 0:
                continue
            distances = [segment_distance_squared(start, end, a, b) for a, b in segments]
            clearance = min(distances) - Fraction(.4) ** 2
            if clearance <= 0:
                continue
            targets = [exact_inside(anchor, vertices, faces[c]) for c in components if len(c) > 100]
            if center_check['inside'] is True and any(x['inside'] is True for x in targets):
                witnesses.append({'anchor_mm': anchor.tolist(), 'box_margin': float(margin),
                                  'squared_capsule_clearance': str(clearance), 'target_checks': targets})
                break
        rows.append({'faces': len(component), 'center_mm': center.tolist(), 'small_center_check': center_check,
                     'area_mm2': float(mesh.area_faces[component].sum()), 'material_path_witnesses': witnesses})
    result = {'updated_at_beijing': beijing_now(), 'source_sha256': digest(__file__), 'mesh_sha256': digest(file), 'rows': rows,
              'scope': '同连续解析材料的单细化负例见证；非整个网格精确嵌入证书'}
    with output.open('x', encoding='utf-8') as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
    print(json.dumps({'small_components': len(rows), 'connected_witnesses': sum(bool(x['material_path_witnesses']) for x in rows)}))


if __name__ == '__main__':
    main()
