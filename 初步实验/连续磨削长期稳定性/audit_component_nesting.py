"""补查小壳是否嵌套在主体内部，区分重复内部壳和材料分离。"""
import argparse
import json
from pathlib import Path
import numpy as np
import pyvista as pv
import trimesh
from audit_component_exact_membership import exact_inside
from timed_paths import beijing_now, digest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, required=True)
    args = parser.parse_args()
    output = args.input / '05-小闭壳与主体精确包含关系.json'
    if output.exists():
        raise ValueError('核查文件禁止覆盖')
    source = args.input / '01-小闭壳材料路径核查.json'
    first = json.loads(source.read_text(encoding='utf-8'))
    rows, cache = [], {}
    for row in first['rows']:
        file = row['file']
        if file not in cache:
            poly = pv.read(file)
            vertices, faces = np.asarray(poly.points), poly.faces.reshape(-1, 4)[:, 1:]
            mesh = trimesh.Trimesh(vertices, faces, process=False)
            components = trimesh.graph.connected_components(mesh.face_adjacency, nodes=np.arange(len(faces)))
            cache = {file: (vertices, faces, components)}
        vertices, faces, components = cache[file]
        small = next(c for c in components if len(c) == row['faces'] and np.array_equal(vertices[np.unique(faces[c])].mean(axis=0), row['center_mm']))
        checks = [exact_inside(np.array(row['center_mm']), vertices, faces[c]) for c in components if len(c) > 100]
        shared = [len(np.intersect1d(np.unique(faces[small]), np.unique(faces[c]))) for c in components if len(c) > 100]
        rows.append({'route': row['route'], 'method': row['method'], 'event': row['event'], 'center_mm': row['center_mm'],
                     'center_in_large_components': checks, 'shared_vertex_counts': shared,
                     'inside_any_large': any(x['inside'] is True for x in checks),
                     'outside_all_large': all(x['inside'] is False for x in checks)})
    result = {'updated_at_beijing': beijing_now(), 'source_sha256': digest(__file__), 'first_audit_sha256': digest(source), 'rows': rows,
              'scope': '有限指定点精确奇偶及原顶点共享关系；非全量嵌入证书'}
    with output.open('x', encoding='utf-8') as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
    print(json.dumps({'rows': len(rows), 'inside_large': sum(x['inside_any_large'] for x in rows),
                      'outside_all_large': sum(x['outside_all_large'] for x in rows),
                      'shared_vertices': sum(sum(x['shared_vertex_counts']) for x in rows)}))


if __name__ == '__main__':
    main()
