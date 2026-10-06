"""检查接缝同步细分、来源继承和固定点，不把细分本身当质量收益。"""

import unittest
import numpy as np
import trimesh
from adaptive_seam import subdivide_constraints
from fragment_pipeline import repair_input


class AdaptiveSeamTests(unittest.TestCase):
    def test_closed_surface_subdivision_preserves_geometry(self):
        mesh = trimesh.creation.box()
        bits = np.ones(len(mesh.faces), dtype=int)
        active = np.arange(len(mesh.faces)) < 2
        result, labels, selected, fixed, parents, record = subdivide_constraints(mesh, bits, active, np.zeros(len(mesh.vertices), bool), 0.4)
        self.assertTrue(result.is_watertight)
        self.assertTrue(result.is_winding_consistent)
        self.assertEqual(result.euler_number, mesh.euler_number)
        self.assertAlmostEqual(result.area, mesh.area)
        self.assertAlmostEqual(result.volume, mesh.volume)
        self.assertGreater(len(record["splits"]), 0)
        self.assertFalse(record["budget_exhausted"])
        np.testing.assert_array_equal(labels, bits[parents])
        np.testing.assert_array_equal(selected, active[parents])
        self.assertTrue(fixed[len(mesh.vertices):].all())

    def test_budget_is_explicit(self):
        mesh = trimesh.creation.box()
        *_, record = subdivide_constraints(mesh, np.ones(12, int), np.ones(12, bool), np.zeros(8, bool), 0.01, max_splits=1)
        self.assertTrue(record["budget_exhausted"])

    def test_fragment_audit_failure_rolls_back(self):
        mesh = trimesh.creation.box()
        result, bits, record = repair_input(mesh, np.ones(12, int), audit=lambda candidate: (False, {"reason": "模拟审计拒绝"}))
        self.assertFalse(record["accepted"])
        np.testing.assert_array_equal(result.vertices, mesh.vertices)
        np.testing.assert_array_equal(result.faces, mesh.faces)


if __name__ == "__main__":
    unittest.main()
