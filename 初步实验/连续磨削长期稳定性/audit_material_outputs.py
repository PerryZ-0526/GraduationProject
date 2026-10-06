"""重新读取实际材料输出，报告提取网格缺陷和方法绑定；不替代精确自交审计。"""
import argparse
import json
from pathlib import Path
import shutil
import numpy as np
import pyvista as pv
import trimesh
from timed_paths import beijing_now, digest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    record_path = args.output / '01-材料长序列记录.json'
    record = json.loads(record_path.read_text(encoding='utf-8'))
    if record['status'] != 'complete' or len(record['rows']) != 12:
        raise ValueError('完整四体三采样率批次尚未终态')
    rows = []
    for row in record['rows']:
        folder = args.output / f"{row['body']}_{row['rate_hz']}Hz"
        path = folder / '03-最终提取网格.vtp'
        poly = pv.read(path)
        faces = poly.faces.reshape(-1, 4)[:, 1:]
        mesh = trimesh.Trimesh(vertices=poly.points, faces=faces, process=False)
        areas = mesh.area_faces
        valid = areas > 1e-12
        minimum = np.degrees(mesh.face_angles.min(axis=1))
        quality = {}
        for threshold in (10, 5, 1):
            small = valid & (minimum < threshold)
            quality[str(threshold)] = {'valid_small_faces': int(np.count_nonzero(small)),
                                      'fraction_of_all_faces': float(np.count_nonzero(small) / len(faces)),
                                      'fraction_of_valid_area': float(areas[small].sum() / areas[valid].sum())}
        events = [json.loads(line) for line in (folder / '01-材料更新事件.jsonl').read_text(encoding='utf-8').splitlines()]
        rows.append({'body': row['body'], 'rate_hz': row['rate_hz'],
                     'saved_hash_matches': digest(path) == row['mesh']['sha256'],
                     'event_count': len(events), 'ordered_complete_events': [e['event_id'] for e in events] == list(range(row['events'])),
                     'finite_vertices': bool(np.isfinite(poly.points).all()),
                     'physical_degenerate_faces': int(np.count_nonzero(~valid)),
                     'watertight': bool(mesh.is_watertight), 'winding_consistent': bool(mesh.is_winding_consistent),
                     'face_components': len(trimesh.graph.connected_components(mesh.face_adjacency, nodes=np.arange(len(faces)))),
                     'small_angles': quality, 'self_intersection_audited': False})
    snapshots = args.output / '方法源码终态副本'
    snapshots.mkdir(exist_ok=False)
    sources = []
    for name in ('material_state.py', 'timed_paths.py', 'run_material_experiment.py', 'audit_material_outputs.py'):
        source = Path(__file__).parent / name
        target = snapshots / name
        shutil.copyfile(source, target)
        sources.append({'file': name, 'sha256': digest(target)})
    result = {'created_at_beijing': beijing_now(), 'record_sha256': digest(record_path),
              'source_binding_scope': '开发终态源码副本；不是未见评价的运行前冻结',
              'sources': sources, 'rows': rows,
              'scope': '重读保存对象、物理面积、连接与角度统计；无连续几何证书或精确自交检查'}
    target = args.output / '02-实际提取网格与开发源码复审.json'
    with target.open('x', encoding='utf-8') as file:
        json.dump(result, file, ensure_ascii=False, indent=2)
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
