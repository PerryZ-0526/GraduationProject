"""验证精确局部谓词和保留原连接的诊断修复，不将其升级为全局证书。"""

import unittest

import numpy as np
import trimesh

from monotone_precision import exact_star_guard, probe_repair


class PrecisionTests(unittest.TestCase):
    def test_inward_and_outward(self):
        before = np.array([[[0., 0., 0.], [1., 0., 0.], [0., 1., 0.]]])
        inward = before.copy()
        inward[0, 0, 2] = -1e-6
        outward = before.copy()
        outward[0, 0, 2] = 1e-6
        self.assertTrue(exact_star_guard(before, inward, [0], before[0, 0], 1e-5))
        self.assertFalse(exact_star_guard(before, outward, [0], before[0, 0], 1e-5))

    def test_budget_and_inversion(self):
        before = np.array([[[0., 0., 0.], [1., 0., 0.], [0., 1., 0.]]])
        over = before.copy()
        over[0, 0, 2] = -2e-5
        inverted = before.copy()
        inverted[0, 0] = [2., 2., 0.]
        self.assertFalse(exact_star_guard(before, over, [0], before[0, 0], 1e-5))
        self.assertFalse(exact_star_guard(before, inverted, [0], before[0, 0], 10.))

    def test_valid_mesh_unchanged(self):
        mesh = trimesh.creation.icosphere(subdivisions=1)
        original_vertices, original_faces = mesh.vertices.copy(), mesh.faces.copy()
        repaired, detail = probe_repair(mesh)
        self.assertTrue(np.array_equal(repaired.vertices, original_vertices))
        self.assertTrue(np.array_equal(repaired.faces, original_faces))
        self.assertTrue(np.array_equal(mesh.vertices, original_vertices))
        self.assertEqual(detail["moves"], [])


if __name__ == "__main__":
    unittest.main()
