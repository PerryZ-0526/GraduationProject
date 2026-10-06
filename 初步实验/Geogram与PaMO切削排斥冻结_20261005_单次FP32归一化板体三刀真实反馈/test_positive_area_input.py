"""输入诊断只区分极小正面积与真退化，不能解除拓扑和非有限检查。"""

import unittest
import numpy as np
import trimesh
from positive_area_input import positive_area_input


class PositiveAreaInputTests(unittest.TestCase):
    def test_tiny_positive_closed_box_is_separate_from_zero(self):
        mesh = trimesh.creation.box(extents=[1e-7] * 3)
        valid, checks = positive_area_input(mesh)
        self.assertTrue(valid)
        self.assertEqual(checks["zero_area_faces"], 0)
        self.assertEqual(checks["historical_area_threshold_counts"]["fp64"], 12)

    def test_true_degenerate_rejected(self):
        mesh = trimesh.creation.box()
        mesh.vertices[0] = mesh.vertices[1]
        valid, checks = positive_area_input(mesh)
        self.assertFalse(valid)
        self.assertGreater(checks["zero_area_faces"], 0)

    def test_open_mesh_rejected(self):
        mesh = trimesh.creation.box()
        mesh.update_faces(np.arange(len(mesh.faces)) != 0)
        valid, _ = positive_area_input(mesh)
        self.assertFalse(valid)

    def test_nonfinite_rejected(self):
        mesh = trimesh.creation.box()
        mesh.vertices[0, 0] = np.nan
        valid, checks = positive_area_input(mesh)
        self.assertFalse(valid)
        self.assertFalse(checks["finite"])


if __name__ == "__main__":
    unittest.main()
