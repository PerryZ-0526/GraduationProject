"""复用合格初始网格显式分项计时，包含式计时不作互斥分项相加。"""
from pathlib import Path
import json
import numpy as np
from joint import load_bone, ProjectedSurface, verified_domain
from dynamic import run_sequence

OUT = Path(__file__).parent/'实验结果'


if __name__ == '__main__':
    import trimesh
    data = np.load(OUT/'joint.npz')
    _, source, _ = load_bone()
    surface = ProjectedSurface(source)
    chart = verified_domain(surface, data['removed'])
    keep = np.ones(len(source.faces), dtype=bool)
    keep[data['removed']] = False
    candidate = dict(vertices=data['vertices'], faces=data['faces'], mapping=data['mapping'],
                     source_ids=data['source_ids'], keep=keep,
                     whole=trimesh.Trimesh(data['whole_vertices'], data['whole_faces'], process=False))
    model, rows = run_sequence(candidate, chart, 2.5)
    summary = {key: float(np.mean([r[key] for r in rows]))
               for key in ('total_ms', 'pipeline_ms', 'certificate_ms', 'height_ms')}
    (OUT/'explicit_profile.json').write_text(json.dumps(dict(mean_ms=summary, records=rows),
                                            ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False), flush=True)
