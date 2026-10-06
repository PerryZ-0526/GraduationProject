"""平面翻边须保持边界、来源和几何，不准仅按小角减少接受非法操作。"""

import unittest
import numpy as np
import trimesh
from planar_quality import improve_planar, minimum_angles


class PlanarQualityTests(unittest.TestCase):
    def source(self):
        return trimesh.Trimesh([[0, 0, 0], [10, 0, 0], [10, 1, 0], [0, 10, 0]], [[0, 1, 3], [1, 2, 3]], process=False)

    def test_planar_quality_improves_without_motion(self):
        source = self.source()
        result, record = improve_planar(source, [1, 1], [False, False])
        self.assertEqual(len(record["flips"]), 1)
        self.assertGreater(minimum_angles(result.vertices, result.faces).min(), minimum_angles(source.vertices, source.faces).min())
        self.assertAlmostEqual(source.area, result.area)
        np.testing.assert_array_equal(source.vertices, result.vertices)

    def test_source_boundary_protected(self):
        source = self.source()
        result, record = improve_planar(source, [1, 2], [False, False])
        self.assertEqual(record["flips"], [])
        np.testing.assert_array_equal(source.faces, result.faces)

    def test_activity_boundary_protected(self):
        result, record = improve_planar(self.source(), [1, 1], [True, False])
        self.assertEqual(record["flips"], [])

    def test_nonplanar_protected(self):
        source = self.source()
        source.vertices[3, 2] = 0.01
        result, record = improve_planar(source, [1, 1], [False, False])
        self.assertEqual(record["flips"], [])

    def test_fixed_edge_protected(self):
        result, record = improve_planar(self.source(), [1, 1], [True, True], protected_vertices=[False, True, False, True])
        self.assertEqual(record["flips"], [])


if __name__ == "__main__":
    unittest.main()
