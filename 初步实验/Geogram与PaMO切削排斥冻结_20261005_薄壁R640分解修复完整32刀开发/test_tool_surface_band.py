"""非凸工具间隙不能被凸化；表面邻域仍固定远离工具的新点。"""
import unittest
import numpy as np
import trimesh
from tool_surface_band import surface_band, triangle_squared_distances


class SurfaceBandTests(unittest.TestCase):
    def test_face_edge_vertex_distance(self):
        triangle = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]], float)
        points = np.array([[.2, .2, .1], [.5, -.1, 0], [-.1, -.1, 0]])
        np.testing.assert_allclose(triangle_squared_distances(points, triangle), [.01, .01, .02], atol=1e-15)

    def test_box_surface_only(self):
        mesh = trimesh.creation.box(extents=[2, 2, 2])
        result = surface_band([[1.05, .173, .281], [1.15, .173, .281], [0, 0, 0]], mesh)
        self.assertEqual(result.tolist(), [True, False, False])

    def test_nonconvex_gap_not_filled(self):
        pieces = []
        for sign in (-1, 1):
            mesh = trimesh.creation.box(extents=[1, 2, 2])
            mesh.apply_translation([sign*2, 0, 0])
            pieces.append(mesh)
        tool = trimesh.util.concatenate(pieces)
        self.assertFalse(tool.is_convex)
        self.assertEqual(surface_band([[0, .173, .281], [1.55, .173, .281]], tool).tolist(), [False, True])

    def test_thin_rotated_triangle(self):
        triangle = np.array([[0, 0, 0], [1, 1, 0], [1, 1+1e-7, 0]])
        point = triangle.mean(axis=0)+[0, 0, .03]
        self.assertAlmostEqual(triangle_squared_distances(np.array([point]), triangle)[0], .0009)

    def test_open_tool_rejected(self):
        tool = trimesh.creation.box()
        tool.update_faces(np.arange(len(tool.faces)-1))
        with self.assertRaises(ValueError):
            surface_band([[0, 0, 0]], tool)

    def test_invalid_margin_rejected(self):
        with self.assertRaises(ValueError):
            surface_band([[0, 0, 0]], trimesh.creation.box(), -1)


if __name__ == "__main__":
    unittest.main()
