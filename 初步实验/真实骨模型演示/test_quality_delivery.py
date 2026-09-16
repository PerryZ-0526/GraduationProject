"""解析真值与交付集成验证，直接运行可复现。"""
import json
from pathlib import Path

import numpy as np
import trimesh

from mesh_quality import removal_metrics, surface_distances, quality
from real_bone_system_demo import to_manifold


def main():
    """用解析盒体证明误切不增加完成度，并验证同面不同三角划分。"""
    initial = to_manifold(trimesh.creation.box(extents=[10, 10, 10]))
    planned_mesh = trimesh.creation.box(extents=[5, 10, 10])
    planned_mesh.apply_translation([2.5, 0, 0])
    planned = to_manifold(planned_mesh)
    wrong_mesh = trimesh.creation.box(extents=[2, 10, 10])
    wrong_mesh.apply_translation([-4, 0, 0])
    wrong = to_manifold(wrong_mesh)
    results = {}
    for name, current, expected_completion, expected_excess in (
        ('initial', initial, 0, 0),
        ('wrong_only', initial - wrong, 0, 200),
        ('planned_only', initial - planned, 100, 0),
        ('planned_and_wrong', initial - planned - wrong, 100, 200)):
        row = removal_metrics(initial.volume(), current, planned)
        assert abs(row['completion_pct'] - expected_completion) < 1e-6, row
        assert abs(row['excess_removed_mm3'] - expected_excess) < 1e-6, row
        results[name] = row
    plane = trimesh.Trimesh([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]],
                            [[0, 1, 2], [0, 2, 3]], process=False)
    refined = plane.subdivide().subdivide()
    assert len(refined.faces) == 16 * len(plane.faces)
    assert abs(refined.area - plane.area) < 1e-12
    distances = surface_distances(refined, plane, samples=1000)
    assert distances['max_mm'] < 1e-12
    equilateral = trimesh.Trimesh([[0, 0, 0], [1, 0, 0], [.5, np.sqrt(3)/2, 0]],
                                  [[0, 1, 2]], process=False)
    assert abs(quality(equilateral)['q_mean'] - 1) < 1e-12
    out = Path(__file__).parent / '网格质量交付实验'
    out.mkdir(exist_ok=True)
    (out / 'analytic_tests.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
    print('PASS: 4 analytic volume cases, subdivision area/distance, equilateral quality')


if __name__ == '__main__':
    main()
