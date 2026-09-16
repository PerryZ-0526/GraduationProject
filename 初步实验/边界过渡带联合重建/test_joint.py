"""边界域验证与精确分离判据的解析反例，避免仅为真实数据报警定制规则。"""
import unittest
import numpy as np
import trimesh
from joint import verified_domain, ProjectedSurface, Rejected
from intersections import separated_xy
from dynamic import JointPatch


class JointTests(unittest.TestCase):
    def test_adaptive_certificate_and_restore(self):
        model = JointPatch.__new__(JointPatch)
        model.samples, model.base_lipschitz = 32, 0.
        model.faces = np.array([[0, 1, 2]])
        model.diameters = np.array([np.sqrt(2.)])
        model.height = lambda xy, tools: np.zeros(xy.shape[:-1])
        vertices = np.array([[0., 0., 0.], [1., 0., 0.], [0., 1., 0.]])
        bounds, sampled, queries = model.certify(vertices, np.array([0]), [], 10.)
        self.assertLessEqual(bounds[0], .1)
        self.assertEqual(sampled, 0.)
        self.assertGreater(queries, 561)
        self.assertEqual(model.samples, 32)

    def test_separation_with_overlapping_boxes(self):
        a = np.array([[0, 0, 0], [2, 0, 0], [0, 2, 0]])
        b = np.array([[2, 2, 0], [2, .5, 0], [.5, 2, 0]])
        self.assertTrue(separated_xy(a, b))

    def test_contact_not_cleared(self):
        a = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]])
        self.assertFalse(separated_xy(a, a))
        self.assertFalse(separated_xy(a, a+[1, 0, 0]))

    def test_crossing_not_cleared(self):
        a = np.array([[0, 0, 0], [2, 0, 0], [0, 2, 0]])
        self.assertFalse(separated_xy(a, a+[.2, .2, 0]))

    def test_domain_box(self):
        box = trimesh.creation.box(extents=[4, 4, 2])
        chart = verified_domain(ProjectedSurface(box), np.flatnonzero(box.face_normals[:, 2] > .9))
        np.testing.assert_array_equal(chart.height(np.array([[.1, .2]])), [1.])
        np.testing.assert_array_equal(chart.height(np.array([[2.+1e-12, .2]])), [1.])
        with self.assertRaises(Rejected):
            chart.height(np.array([[2.+1e-6, .2]]))

    def test_domain_occluded(self):
        box = trimesh.creation.box(extents=[4, 4, 2])
        upper = box.copy()
        upper.apply_translation([0, 0, 3])
        stacked = trimesh.util.concatenate([box, upper])
        with self.assertRaises(Rejected):
            verified_domain(ProjectedSurface(stacked), np.flatnonzero(box.face_normals[:, 2] > .9))


if __name__ == '__main__':
    unittest.main()
