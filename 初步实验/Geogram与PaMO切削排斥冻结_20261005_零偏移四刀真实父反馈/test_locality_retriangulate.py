"""验证退化触发、来源边界和几何凸性，防止翻边侵入其他曲面。"""

import unittest
import numpy as np
import trimesh

from locality_retriangulate import repair_degenerate


class RetriangulateTests(unittest.TestCase):
    def mesh(self, height=0):
        # 第三点在旧对角线上，旧两面退化为带边界分点的单个三角区域。
        return trimesh.Trimesh([[0, 0, 0], [1, 0, 0], [0.5, height, 0], [0, -1, 0]],
                              [[0, 1, 2], [1, 0, 3]], process=False)

    def test_coplanar_degenerate_face_repaired_without_vertex_motion(self):
        original = self.mesh()
        mesh, bits, record = repair_degenerate(original, [1, 1])
        self.assertEqual(record["remaining_invalid_faces"], 0)
        self.assertEqual(len(record["flips"]), 1)
        np.testing.assert_array_equal(mesh.vertices, original.vertices)
        np.testing.assert_array_equal(bits, [1, 1])
        self.assertAlmostEqual(mesh.area, original.area)

    def test_source_boundary_cannot_flip(self):
        mesh, bits, record = repair_degenerate(self.mesh(), [1, 2])
        self.assertEqual(record["flips"], [])
        self.assertEqual(record["remaining_invalid_faces"], 1)

    def test_valid_low_angle_face_does_not_trigger(self):
        original = self.mesh(1e-5)
        mesh, bits, record = repair_degenerate(original, [1, 1])
        self.assertEqual(record["flips"], [])
        np.testing.assert_array_equal(mesh.faces, original.faces)

    def test_nonplanar_quad_rejected(self):
        # 极短公共边使第一面面积退化，但其离第二面的平面仍超过预算。
        original = trimesh.Trimesh([[0, 0, 0], [1e-6, 0, 0], [0.5e-6, 0, 1e-6], [0, -1, 0]],
                                  [[0, 1, 2], [1, 0, 3]], process=False)
        mesh, bits, record = repair_degenerate(original, [1, 1])
        self.assertEqual(record["flips"], [])


if __name__ == "__main__":
    unittest.main()
