"""初态编码锚点规则的坐标与物理有效性回归。"""
import unittest
import numpy as np
from encoded_degenerate_anchors import initial_encoding_anchors


class InitialAnchorTests(unittest.TestCase):
    def test_encoded_only_degenerate(self):
        vertices = np.array([[1., 0., 0.], [1.+1e-8, 0., 0.], [1., 1., 0.]])
        before = vertices.copy()
        mask, record = initial_encoding_anchors(vertices, [[0, 1, 2]], [True, False, False], 1., np.zeros(3))
        self.assertTrue(mask.all())
        self.assertEqual(record['added_vertices'], [1, 2])
        np.testing.assert_array_equal(vertices, before)

    def test_regular_face_unchanged(self):
        mask, record = initial_encoding_anchors(np.eye(3), [[0, 1, 2]], [True, False, False], 1., np.zeros(3))
        np.testing.assert_array_equal(mask, [True, False, False])
        self.assertEqual(record['added_vertices'], [])

    def test_physical_zero_rejected(self):
        with self.assertRaises(ValueError):
            initial_encoding_anchors(np.zeros((3, 3)), [[0, 1, 2]], [True]*3, 1., np.zeros(3))

    def test_nonfinite_rejected(self):
        vertices = np.eye(3)
        vertices[0, 0] = np.nan
        with self.assertRaises(ValueError):
            initial_encoding_anchors(vertices, [[0, 1, 2]], [True]*3, 1., np.zeros(3))


if __name__ == '__main__':
    unittest.main()
