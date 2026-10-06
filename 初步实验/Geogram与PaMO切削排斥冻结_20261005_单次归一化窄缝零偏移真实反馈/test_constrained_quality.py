"""核对新顶点、外部面绕序、零自由度及全顶点距离见证。"""

import unittest
import numpy as np
import trimesh

from constrained_quality import fixed_surface_contract, safe_project
from run_constrained_feedback import global_geometry


class ConstrainedQualityTests(unittest.TestCase):
    def setUp(self):
        self.source = trimesh.creation.box()
        self.active = np.zeros(len(self.source.faces), dtype=bool)
        self.active[0] = True
        self.fixed = np.ones(len(self.source.vertices), dtype=bool)

    def test_new_vertex_in_active_triangle_is_allowed(self):
        triangle = self.source.faces[0]
        middle = self.source.vertices[triangle].mean(axis=0)
        vertices = np.vstack((self.source.vertices, middle))
        new_id = len(vertices) - 1
        a, b, c = triangle
        faces = np.vstack((self.source.faces[1:], [[a, b, new_id], [b, c, new_id], [c, a, new_id]]))
        candidate = trimesh.Trimesh(vertices, faces, process=False)
        self.assertTrue(fixed_surface_contract(self.source, candidate, self.active, self.fixed)["passed"])
        self.assertTrue(candidate.is_watertight)

    def test_fixed_vertex_or_outside_orientation_change_is_rejected(self):
        candidate = self.source.copy()
        candidate.vertices[0, 0] += 1e-8
        self.assertFalse(fixed_surface_contract(self.source, candidate, self.active, self.fixed)["passed"])
        candidate = self.source.copy()
        candidate.faces[1] = candidate.faces[1][::-1]
        self.assertFalse(fixed_surface_contract(self.source, candidate, self.active, self.fixed)["passed"])

    def test_zero_free_dofs_return_identity_without_cuda(self):
        output, details = safe_project(self.source, self.source, np.arange(len(self.fixed)), self.fixed)
        np.testing.assert_array_equal(output.vertices, self.source.vertices)
        self.assertEqual(details["safe_projection_ms"], 0)
        output.vertices[0, 0] += .1
        self.assertNotEqual(output.vertices[0, 0], self.source.vertices[0, 0])

    def test_all_vertices_probe_finds_known_translation(self):
        target = self.source.copy()
        target.apply_translation([.12, 0, 0])
        result = global_geometry(self.source, target)
        self.assertAlmostEqual(result["all_vertices_probe_max_mm"], .12, places=12)
        self.assertGreater(result["probe_max_mm"], .1)
        self.assertFalse(result["continuous_geometry_certified"])


if __name__ == "__main__":
    unittest.main()
