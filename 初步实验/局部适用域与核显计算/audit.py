"""重读逐状态质量、外部不变性，并用独立原面射线对拍末态。"""
import json
import numpy as np
from experiment import OUT, load_candidate
from joint import mesh_quality
from real_patch import local_trajectory


if __name__ == '__main__':
    candidate, chart = load_candidate()
    comparison = json.loads((OUT/'comparison.json').read_text(encoding='utf-8'))
    results = []
    outside = np.unique(candidate['whole'].faces[:-len(candidate['faces'])])
    for run in comparison['runs']:
        data = np.load(OUT/f"{run['method']}_{run['z']}.npz")
        states, faces = data['snapshots'], data['faces']
        for state in states:
            q, angle, area = mesh_quality(state, faces)
            assert q.min() >= .4 and angle.min() >= 25 and area.min() > 1e-12
            whole = candidate['whole'].vertices.copy()
            whole[data['mapping']] = state
            np.testing.assert_array_equal(whole[outside], candidate['whole'].vertices[outside])
            np.testing.assert_array_equal(state[:, :2], states[0, :, :2])
        rng = np.random.default_rng(20260907)
        _, _, area = mesh_quality(states[-1], faces)
        ids = rng.choice(len(faces), 10000, p=area/area.sum())
        uv = rng.random((10000, 2))
        root = np.sqrt(uv[:, 0])
        bary = np.column_stack([1-root, root*(1-uv[:, 1]), root*uv[:, 1]])
        points = np.sum(bary[..., None]*states[-1][faces[ids]], axis=1)
        target = chart.surface.query(points[:, :2])['z']
        for tool in local_trajectory(run['z'])[:run['accepted']]:
            a, b = np.array(tool.start), np.array(tool.end)
            t = np.clip(np.sum((points[:, :2]-a)*(b-a), axis=1)/np.sum((b-a)**2), 0., 1.)
            squared = np.sum((points[:, :2]-a-t[:, None]*(b-a))**2, axis=1)
            inside = squared <= tool.radius**2
            target[inside] = np.minimum(target[inside], tool.z-np.sqrt(tool.radius**2-squared[inside]))
        errors = np.abs(points[:, 2]-target)
        assert np.isfinite(errors).all() and np.all(errors <= data['bounds'][ids]+1e-9)
        results.append(dict(method=run['method'], z=run['z'], states=len(states), outside_unchanged=True,
            samples=10000, seed=20260907, mean_mm=float(errors.mean()), p95_mm=float(np.percentile(errors, 95)),
            p99_mm=float(np.percentile(errors, 99)), max_mm=float(errors.max())))
    (OUT/'audit.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(results, ensure_ascii=False))
