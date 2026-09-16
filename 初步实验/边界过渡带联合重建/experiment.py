"""同源同域的固定边界、两项消融及联合方法对照，并保存逐状态整骨拼接证据。"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
from hashlib import sha256
from time import perf_counter
import json
import platform
import numpy as np
from joint import load_bone, ProjectedSurface, verify_chart, solve
from dynamic import run_sequence

OUT = Path(__file__).parent/'实验结果'


def main():
    OUT.mkdir(exist_ok=True)
    original, source, transform = load_bone()
    surface = ProjectedSurface(source)
    verified, polygons = verify_chart(surface, 8.)
    assert verified['accepted']
    initial_ids = np.array([i for i in polygons if np.max(np.abs(source.triangles[i, :, :2])) < 8.])
    result = dict(timestamp=datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S'),
                  python=platform.python_version(), platform=platform.platform(),
                  source_sha256=sha256(original.vertices.tobytes()+original.faces.tobytes()).hexdigest(),
                  area_mm2=.0125, width_mm=8., max_iterations=16,
                  boundary_tolerance_mm=1e-10, methods=[], sequences=[], code_sha256={})
    files = list(Path(__file__).parent.glob('*.py'))
    files += [Path(__file__).parents[1]/'真实骨面共边拼接/stitch.py',
              Path(__file__).parents[1]/'局部区域重建阶段一/patch_model.py']
    result['code_sha256'] = {str(p.relative_to(Path(__file__).parents[1])): sha256(p.read_bytes()).hexdigest() for p in files}
    for name, expand, refine in [('fixed', False, False), ('refine_only', False, True),
                                  ('expand_only', True, False), ('joint', True, True)]:
        started = perf_counter()
        candidate, chart, history, removed = solve(surface, initial_ids, expand=expand, refine=refine)
        result['methods'].append(dict(name=name, expand=expand, refine=refine,
                                      elapsed_ms=(perf_counter()-started)*1000, history=history))
        np.savez_compressed(OUT/f'{name}.npz', vertices=candidate['vertices'], faces=candidate['faces'],
                            whole_vertices=candidate['whole'].vertices, whole_faces=candidate['whole'].faces,
                            removed=removed, source_ids=candidate['source_ids'], mapping=candidate['mapping'],
                            raw_intersection_flags=candidate['intersection_flags'], transform=transform)
        if name == 'joint' and history[-1]['accepted']:
            for z in (2.95, 2.5, 1.8):
                model, records = run_sequence(candidate, chart, z)
                successful = [r for r in records if r['accepted']]
                result['sequences'].append(dict(z=z, records=records, accepted_steps=len(successful),
                    changed_steps=int(sum(np.any(np.abs(b[:, 2]-a[:, 2]) > 1e-10)
                                          for a, b in zip(model.snapshots[:-1], model.snapshots[1:]))),
                    max_removal_mm=float(np.max(model.snapshots[0][:, 2]-model.vertices[:, 2])),
                    max_total_ms=float(max(r['total_ms'] for r in records)),
                    mean_total_ms=float(np.mean([r['total_ms'] for r in records]))))
                np.savez_compressed(OUT/f'sequence_z{z:g}.npz', vertices=model.vertices, faces=model.faces,
                                    snapshots=np.asarray(model.snapshots), bounds=model.bounds,
                                    whole_faces=candidate['whole'].faces, mapping=candidate['mapping'],
                                    original_whole_vertices=candidate['whole'].vertices, transform=transform)
        (OUT/'results.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(OUT/'results.json', flush=True)


if __name__ == '__main__':
    main()
