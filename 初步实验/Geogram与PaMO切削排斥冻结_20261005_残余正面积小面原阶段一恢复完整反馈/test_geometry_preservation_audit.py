"""核对自适应距离区间及未切削区域判定的必要边界行为。"""

import unittest
import numpy as np
import trimesh

from geometry_preservation_audit import MeshDistance, clearance, directed_interval, mesh_valid, triangle_separation_gap
from audit_pamo_outputs import as_polydata


class GeometryAuditTest(unittest.TestCase):
    def test_separation_excludes_disjoint_but_keeps_crossing_triangles(self):
        a = np.array([[0., 0., 0.], [1., 0., 0.], [0., 1., 0.]])
        self.assertGreater(triangle_separation_gap(a, a + [2., 2., 0.]), .1)
        self.assertEqual(triangle_separation_gap(a, a + [.1, .1, 0.]), 0)
        b = np.array([[.2, .2, -1.], [.2, .2, 1.], [.8, .2, 0.]])
        self.assertEqual(triangle_separation_gap(a, b), 0)

    def test_component_count_does_not_repair_open_surface(self):
        mesh = trimesh.Trimesh([[0, 0, 0], [1, 0, 0], [0, 1, 0]], [[0, 1, 2]], process=False)
        valid, result = mesh_valid(mesh)
        self.assertFalse(valid)
        self.assertEqual(result["components"], 1)
        self.assertEqual(len(mesh.faces), 1)

    def test_parallel_triangle_interval(self):
        source = trimesh.Trimesh([[0, 0, 0], [.1, 0, 0], [0, .1, 0]], [[0, 1, 2]], process=False)
        target = source.copy()
        target.apply_translation([0, 0, .02])
        result = directed_interval(as_polydata(source), as_polydata(target), tolerance=.002,
                                   max_cells=20000, decision_budget=0)
        self.assertLessEqual(result["lower_mm"], .02 + 1e-12)
        self.assertGreaterEqual(result["upper_mm"], .02 - 1e-12)
        self.assertLessEqual(result["upper_mm"] - result["lower_mm"], .002 + 1e-12)
        self.assertFalse(result["certified_continuous_geometry"])

    def test_refinement_budget_keeps_conservative_radius(self):
        source = trimesh.Trimesh([[0, 0, 0], [1, 0, 0], [0, 1, 0]], [[0, 1, 2]], process=False)
        target = trimesh.Trimesh([[0, 0, .01], [.05, 0, .01], [0, .05, .01]], [[0, 1, 2]], process=False)
        interval = directed_interval(as_polydata(source), as_polydata(target), max_cells=5, decision_budget=0)
        distances = MeshDistance(as_polydata(target))(source.vertices)
        self.assertLessEqual(interval["lower_mm"], float(distances.max()) + 1e-12)
        self.assertGreaterEqual(interval["upper_mm"], float(distances.max()) - 1e-12)

    def test_capsule_mask_has_no_ct_transition_bridge(self):
        primitives = [{"start": np.array([0., 0., 0.]), "end": np.array([1., 0., 0.]), "radius": .1},
                      {"start": np.array([0., 1., 0.]), "end": np.array([1., 1., 0.]), "radius": .1}]
        values = clearance(np.array([[.5, 0, 0], [.5, .5, 0], [.5, 1, 0]]), primitives)
        self.assertLess(values[0], 0)
        self.assertGreater(values[1], .1)
        self.assertLess(values[2], 0)


if __name__ == "__main__":
    unittest.main()
