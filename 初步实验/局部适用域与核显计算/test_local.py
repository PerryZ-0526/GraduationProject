"""验证上界使用连续原面、排除远处高面，并明确拒绝域外与非法参数。"""
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import numpy as np
from local_model import footprint_ceiling, Rejected, LocalPatch, JointPatch
from patch_model import Sweep


class LocalTests(unittest.TestCase):
    def setUp(self):
        self.triangles = np.array([[[0., 0., 0.], [4., 0., 4.], [0., 4., 0.]],
                                   [[10., 10., 20.], [11., 10., 20.], [10., 11., 20.]]])

    def test_affine_clipped_maximum(self):
        tool = Sweep((1., 1.), (1., 1.), .25, 2.)
        self.assertAlmostEqual(footprint_ceiling(self.triangles, tool), 1.25, places=7)

    def test_high_face_inside_is_retained(self):
        tool = Sweep((10., 10.), (10., 10.), 1., 21.)
        self.assertGreaterEqual(footprint_ceiling(self.triangles, tool), 20.)

    def test_empty_and_invalid(self):
        for tool in [Sweep((30., 30.), (30., 30.), 1., 2.), Sweep((0., 0.), (0., 0.), -1., 2.)]:
            with self.assertRaises(Rejected):
                footprint_ceiling(self.triangles, tool)

    def test_sampled_capsule_below_bound(self):
        rng = np.random.default_rng(20260907)
        tool = Sweep((1., 1.), (2., 1.), .3, 4.)
        points = rng.uniform([.7, .7], [2.3, 1.3], (10000, 2))
        self.assertTrue(np.all(points[:, 0] <= footprint_ceiling(self.triangles, tool)))

    def test_history_rejection_restores_ceiling(self):
        model = LocalPatch.__new__(LocalPatch)
        model.ceiling, model.attempts = 20., []
        model.chart = SimpleNamespace(ids=np.arange(2), surface=SimpleNamespace(mesh=SimpleNamespace(triangles=self.triangles)))
        model.tools = [Sweep((1., 1.), (1., 1.), .25, 2.)]
        with self.assertRaises(Rejected):
            model.update(Sweep((10., 10.), (10., 10.), 1., 21.))
        self.assertEqual(model.ceiling, 20.)
        self.assertEqual(len(model.tools), 1)
        self.assertFalse(model.attempts[-1]['accepted'])

    def test_parent_failure_restores_ceiling(self):
        model = LocalPatch.__new__(LocalPatch)
        model.ceiling, model.tools, model.attempts = 20., [], []
        model.chart = SimpleNamespace(ids=np.arange(2), surface=SimpleNamespace(mesh=SimpleNamespace(triangles=self.triangles)))
        with patch.object(JointPatch, 'update', side_effect=Rejected('边界拒绝')):
            with self.assertRaises(Rejected):
                model.update(Sweep((1., 1.), (1., 1.), .25, 2.))
        self.assertEqual(model.ceiling, 20.)
        self.assertEqual(model.tools, [])


if __name__ == '__main__':
    unittest.main()
