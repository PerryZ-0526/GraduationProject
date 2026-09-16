"""分层曲面几何与共边拓扑测试；不以单元测试代替整套质量验收。"""
import unittest
import numpy as np
from axis_patch import generate, residual, exact_distance


class AxisTests(unittest.TestCase):
    def test_shared_seams_and_open_disk(self):
        for z in (1.8, .5, 0., -1., -3.):
            mesh, labels, seams = generate(z)
            self.assertEqual(mesh.euler_number, 1)
            self.assertTrue(mesh.is_winding_consistent)
            edges, counts = np.unique(np.sort(mesh.edges, axis=1), axis=0, return_counts=True)
            self.assertTrue(np.all(counts <= 2))
            boundary = edges[counts == 1]
            np.testing.assert_allclose(np.linalg.norm(mesh.vertices[boundary, :2], axis=2), 4., atol=1e-12)
            self.assertEqual(len(seams), 2 if z < 0 else 1)
            for face, label in zip(mesh.triangles, labels):
                self.assertLess(np.max(residual(face, label, z)), 1e-12)

    def test_vertical_wall_is_not_height_graph(self):
        mesh, labels, _ = generate(-1.)
        wall = mesh.triangles[labels == 'cylinder']
        self.assertGreater(len(wall), 0)
        self.assertGreater(np.ptp(wall[..., 2]), .9)
        self.assertTrue(np.all(np.abs(mesh.face_normals[labels == 'cylinder', 2]) < 1e-12))

    def test_no_contact_and_invalid_rejected(self):
        for z in (2., 3., np.nan):
            with self.assertRaises(ValueError):
                generate(z)

    def test_finite_surface_distance(self):
        # 最近点可在底部、圆柱侧壁或有限外圆周，不允许投影到无限平面而低估距离。
        points = np.array([[0., 0., -3.], [2.1, 0., -.5], [5., 0., 0.]])
        np.testing.assert_allclose(exact_distance(points, -1.), [0., .1, 1.], atol=1e-12)

    def test_smooth_seam_ablation(self):
        from experiment import quality
        for z in (-.0001, -.05):
            strict = generate(z)[0]
            smooth = generate(z, preserve_tangent_seam=False)[0]
            self.assertFalse(quality(strict)['shape_pass'])
            self.assertTrue(quality(smooth)['shape_pass'])
            self.assertTrue(smooth.is_winding_consistent)
            self.assertEqual(smooth.euler_number, 1)


if __name__ == '__main__':
    unittest.main()
