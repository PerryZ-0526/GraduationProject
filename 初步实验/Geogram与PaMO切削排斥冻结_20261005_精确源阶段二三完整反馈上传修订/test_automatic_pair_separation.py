"""验证分离证据与凸投影边界，不用实现镜像代替真实精确负例。"""

import unittest
import sys
from pathlib import Path
import numpy as np
import trimesh
# 独立测试入口显式添加同目录模块，并初始化既有公共审计依赖路径。
sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_constrained_batch
from automatic_pair_separation import original_pair_separator, exact_pair_separated, project_vertices


class SeparationTests(unittest.TestCase):
    def setUp(self):
        self.a = np.array([[0., 0., 0.], [1., 0., 0.], [0., 1., 0.]])

    def test_thin_opposite_faces_have_exact_plane(self):
        b = self.a + [0., 0., .03]
        plane = original_pair_separator(self.a, b)
        self.assertIsNotNone(plane)
        self.assertTrue(exact_pair_separated((self.a, b), plane['normal'], plane['offset']))

    def test_crossing_faces_are_not_original_separator_sources(self):
        b = np.array([[.25, .25, -1.], [.25, .25, 1.], [.75, .25, 0.]])
        self.assertIsNone(original_pair_separator(self.a, b))

    def test_shared_boundary_does_not_get_strict_gap(self):
        self.assertIsNone(original_pair_separator(self.a, self.a[[1, 2, 0]]))

    def test_large_world_translation_keeps_exact_evidence(self):
        a = self.a + [1e9, -1e9, 1e9]
        b = a + [0., 0., .03]
        plane = original_pair_separator(a, b)
        self.assertIsNotNone(plane)
        self.assertTrue(exact_pair_separated((a, b), plane['normal'], plane['offset']))

    def test_guard_changes_motion_direction_without_crossing(self):
        raw = trimesh.Trimesh(self.a, [[0, 1, 2]], process=False)
        items = [(np.array([1., 0., 1.]), .05), (np.array([0., 0., -1.]), -.01)]
        mesh, error = project_vertices(raw, [items, items, items], .1)
        self.assertIsNone(error)
        self.assertTrue(np.all(mesh.vertices[:, 2] <= .01 + 1e-10))
        self.assertTrue(np.all(mesh.vertices[:, 0] + mesh.vertices[:, 2] >= .05 - 1e-10))

    def test_insufficient_budget_rejects(self):
        raw = trimesh.Trimesh(self.a, [[0, 1, 2]], process=False)
        items = [(np.array([0., 0., 1.]), .5)]
        mesh, error = project_vertices(raw, [items, items, items], .1)
        self.assertIsNone(mesh)
        self.assertEqual(error['reason'], 'infeasible_or_unverified_projection')


if __name__ == '__main__':
    unittest.main()
