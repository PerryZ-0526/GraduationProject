"""相同整骨初态、交叉轨迹、验收门槛的全域与局部判据对照。"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import json
import numpy as np
import trimesh
from local_model import LocalPatch
from dynamic import JointPatch, run_sequence
from joint import load_bone, ProjectedSurface, verified_domain

OUT = Path(__file__).parent/'实验结果'


def load_candidate():
    data = np.load(Path(__file__).parents[1]/'边界过渡带联合重建/实验结果/joint.npz')
    _, source, _ = load_bone()
    chart = verified_domain(ProjectedSurface(source), data['removed'])
    keep = np.ones(len(source.faces), dtype=bool)
    keep[data['removed']] = False
    candidate = dict(vertices=data['vertices'], faces=data['faces'], mapping=data['mapping'],
                     source_ids=data['source_ids'], keep=keep,
                     whole=trimesh.Trimesh(data['whole_vertices'], data['whole_faces'], process=False))
    return candidate, chart


if __name__ == '__main__':
    OUT.mkdir(exist_ok=True)
    candidate, chart = load_candidate()
    result = dict(time_bjt=datetime.now(timezone(timedelta(hours=8))).isoformat(), runs=[])
    for z in (2.95, 2.5, 1.8, 0.):
        for name, factory in [('global', JointPatch), ('local', LocalPatch)]:
            print(name, z, flush=True)
            model, rows = run_sequence(candidate, chart, z, model_factory=factory)
            snapshots = np.asarray(model.snapshots)
            np.savez_compressed(OUT/f'{name}_{z}.npz', snapshots=snapshots, faces=model.faces,
                                bounds=model.bounds, mapping=candidate['mapping'])
            result['runs'].append(dict(method=name, z=z, accepted=sum(r['accepted'] for r in rows),
                changed=sum(not np.array_equal(a, b) for a, b in zip(snapshots[:-1], snapshots[1:])),
                max_removal_mm=float((snapshots[0, :, 2]-snapshots[-1, :, 2]).max()), records=rows))
            (OUT/'comparison.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
