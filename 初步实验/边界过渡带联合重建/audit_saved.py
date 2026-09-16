"""重新读取保存状态，独立射线查询原面并核对外部不变与逐面质量。"""
from pathlib import Path
import json
import numpy as np
from joint import load_bone, ProjectedSurface, mesh_quality
from real_patch import local_trajectory

OUT = Path(__file__).parent/'实验结果'


def main():
    _, source, _ = load_bone()
    surface = ProjectedSurface(source)
    results = []
    for z in (2.95, 2.5):
        data = np.load(OUT/f'sequence_z{z:g}.npz')
        snapshots, faces = data['snapshots'], data['faces']
        outside = np.unique(data['whole_faces'][:-len(faces)])
        min_angles = []
        for vertices in snapshots:
            q, angles, area2 = mesh_quality(vertices, faces)
            assert q.min() >= .4 and angles.min() >= 25 and area2.min() > 1e-12
            min_angles.append(float(angles.min()))
            whole = data['original_whole_vertices'].copy()
            whole[data['mapping']] = vertices
            np.testing.assert_array_equal(whole[outside], data['original_whole_vertices'][outside])
            np.testing.assert_array_equal(vertices[:, :2], snapshots[0][:, :2])
        rng = np.random.default_rng(20260907)
        vertices = snapshots[-1]
        _, _, area2 = mesh_quality(vertices, faces)
        ids = rng.choice(len(faces), 10000, p=area2/area2.sum())
        uv = rng.random((10000, 2))
        root = np.sqrt(uv[:, 0])
        weights = np.column_stack([1-root, root*(1-uv[:, 1]), root*uv[:, 1]])
        points = np.sum(weights[..., None]*vertices[faces[ids]], axis=1)
        target = surface.query(points[:, :2])['z']
        for tool in local_trajectory(z):
            a, b = np.array(tool.start), np.array(tool.end)
            t = np.clip(np.sum((points[:, :2]-a)*(b-a), axis=1)/np.sum((b-a)**2), 0, 1)
            d2 = np.sum((points[:, :2]-a-t[:, None]*(b-a))**2, axis=1)
            inside = d2 <= tool.radius**2
            target[inside] = np.minimum(target[inside], tool.z-np.sqrt(tool.radius**2-d2[inside]))
        errors = np.abs(target-points[:, 2])
        assert np.all(np.isfinite(errors)) and np.all(errors <= data['bounds'][ids]+1e-9)
        results.append(dict(z=z, saved_states=len(snapshots), outside_unchanged=True,
                            min_angle_deg=min(min_angles), seed=20260907, final_samples=10000,
                            sample_mean_mm=float(errors.mean()), sample_p95_mm=float(np.percentile(errors, 95)),
                            sample_p99_mm=float(np.percentile(errors, 99)), sample_max_mm=float(errors.max())))
    (OUT/'independent_audit.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(results, ensure_ascii=False))


if __name__ == '__main__':
    main()
