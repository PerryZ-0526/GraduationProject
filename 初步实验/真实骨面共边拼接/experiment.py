"""真实CT固定共边拼接的预注册参数矩阵，保留全部成功与失败候选。"""
from datetime import datetime, timezone, timedelta
from hashlib import sha256
import json
import platform
from itertools import product
from time import perf_counter
from pathlib import Path
import numpy as np
import pymeshlab
from stitch import (load_bone, ProjectedSurface, verify_chart, BoneChart, stitch_candidate,
                    audit_candidate, mesh_quality, Rejected)

OUT = Path(__file__).parent/'实验结果'


def main():
    OUT.mkdir(exist_ok=True)
    original, source, transform = load_bone()
    surface = ProjectedSurface(source)
    results = dict(timestamp=datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S'),
                   python=platform.python_version(), platform=platform.platform(), processor=platform.processor(),
                   source_faces=len(source.faces), source_vertices=len(source.vertices),
                   source_geometry_sha256=sha256(original.vertices.tobytes()+original.faces.tobytes()).hexdigest(),
                   triangle_version=__import__('triangle').__version__,
                   code_sha256={p.name: sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob('*.py')},
                   thresholds=dict(min_q=.4, min_angle_deg=25, max_vertical_error_mm=.1), runs=[])
    baseline = pymeshlab.MeshSet()
    baseline.add_mesh(pymeshlab.Mesh(source.vertices, source.faces))
    baseline.compute_selection_by_self_intersections_per_face()
    results['source_self_intersection_flags'] = int(baseline.current_mesh().selected_face_number())
    for width in (6., 8.):
        verified, polygons = verify_chart(surface, width)
        if not verified['accepted']:
            raise Rejected('预设图域未通过前置验证')
        chart = BoneChart(surface, polygons)
        removed = np.array([i for i in polygons if np.max(np.abs(source.triangles[i, :, :2])) < width])
        for graded, area in product((False, True), (.1, .04, .0125)):
            started = perf_counter()
            candidate = stitch_candidate(source, removed, chart, area, graded)
            audit, errors, angles = audit_candidate(surface, candidate)
            flags = candidate['intersection_flags']
            _, outside_angles, _ = mesh_quality(source.vertices, source.faces[candidate['keep']])
            audit.update(half_width_mm=width, area_parameter_mm2=area, graded=graded, removed_faces=len(removed),
                         outside_min_angle_deg=float(outside_angles.min()),
                         build_audit_ms=(perf_counter()-started)*1000,
                         shared_boundary_vertices=len(candidate['source_ids']))
            results['runs'].append(audit)
            np.savez_compressed(OUT/f'candidate_w{width:g}_a{area:g}_g{int(graded)}.npz',
                                vertices=candidate['vertices'], faces=candidate['faces'],
                                whole_vertices=candidate['whole'].vertices, whole_faces=candidate['whole'].faces,
                                source_ids=candidate['source_ids'], removed=removed,
                                error=errors, angles=angles, intersection_flags=flags, transform=transform)
            print(json.dumps(audit, ensure_ascii=False), flush=True)
    # JSON由实验入口生成，原输入和其他阶段证据均不覆盖。
    (OUT/'results.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
