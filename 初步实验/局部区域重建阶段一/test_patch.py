"""先定义解析高度图原型必须满足的行为，不用真实骨面替代解析真值。"""
import unittest
import numpy as np
from patch_model import PatchModel, Sweep, height, Rejected


class PatchTests(unittest.TestCase):
    def test_sphere_and_capsule_truth(self):
        tool = Sweep((-1., 0.), (1., 0.), 2., 1.5)
        values = height(np.array([[0., 0.], [1., 1.], [4., 0.]]), 'plane', [tool])
        np.testing.assert_allclose(values, [-.5, 1.5-np.sqrt(3), 0.], atol=1e-12)

    def test_tangent_and_repeat(self):
        model = PatchModel(.2)
        original = model.vertices.copy()
        model.update(Sweep((0., 0.), (0., 0.), 2., 2.))
        np.testing.assert_array_equal(original, model.vertices)
        cut = Sweep((-.5, .07), (.5, .07), 2., 1.6)
        model.update(cut)
        once = model.vertices.copy()
        model.update(cut)
        np.testing.assert_array_equal(once, model.vertices)

    def test_boundary_rejection_is_atomic(self):
        model = PatchModel(.2)
        original = model.vertices.copy()
        with self.assertRaises(Rejected):
            model.update(Sweep((3.9, 0.), (3.9, 0.), 2., 1.5))
        np.testing.assert_array_equal(original, model.vertices)
        self.assertEqual(len(model.tools), 0)

    def test_geometry_is_not_inherited_from_mesh(self):
        model = PatchModel(.2)
        cut = Sweep((-.5, .07), (.5, .07), 2., 1.6)
        model.update(cut)
        np.testing.assert_allclose(model.vertices[:, 2], height(model.xy, 'plane', [cut]))
        self.assertTrue(np.all(model.vertices[model.boundary, 2] == 0.))

    def test_order_independence_and_surface_orientation(self):
        cuts = [Sweep((-.7, .037), (.7, .037), 2., 1.5),
                Sweep((.037, -.7), (.037, .7), 2., 1.5)]
        forward, backward = PatchModel(.2), PatchModel(.2)
        for cut in cuts:
            forward.update(cut)
        for cut in reversed(cuts):
            backward.update(cut)
        np.testing.assert_array_equal(forward.vertices, backward.vertices)
        tri = forward.vertices[forward.faces]
        normals = np.cross(tri[:, 1]-tri[:, 0], tri[:, 2]-tri[:, 0])
        self.assertTrue(np.all(normals[:, 2] > 0))
        self.assertGreaterEqual(forward.q.min(), .4)
        self.assertGreaterEqual(forward.angles.min(), 25)

    def test_quality_rejection_does_not_commit(self):
        model = PatchModel(.2)
        original = model.vertices.copy()
        with self.assertRaises(Rejected):
            model.update(Sweep((.037, .021), (.037, .021), 2., .02))
        np.testing.assert_array_equal(original, model.vertices)
        self.assertEqual(model.tools, [])


if __name__ == '__main__':
    unittest.main()
