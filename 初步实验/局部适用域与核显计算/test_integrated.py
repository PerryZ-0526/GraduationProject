"""需要真实核显的集成测试：连续变长缓冲、空历史以及错误输出拒绝。"""
import unittest
from unittest.mock import patch
import numpy as np
from experiment import load_candidate
from integrated import SweepDevice, CheckedGpuPatch, Rejected, cpu_sweep
from real_patch import local_trajectory


class IntegratedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.device = SweepDevice()

    def test_resize_and_empty_history(self):
        rng = np.random.default_rng(20260908)
        for n, m in [(4, 1), (200, 16), (3, 2), (1, 0)]:
            xy, base = rng.uniform(-4, 4, (n, 2)), rng.uniform(-1, 1, n)
            tools = np.array([[0., 0., 0., 0., 3., 2.5]]*m).reshape(-1, 6)
            np.testing.assert_allclose(self.device.evaluate(xy, base, tools), cpu_sweep(xy, base, tools), atol=1e-10, rtol=0.)

    def test_bad_gpu_output_rolls_back(self):
        candidate, chart = load_candidate()
        model = CheckedGpuPatch(chart, candidate, self.device)
        before = model.vertices.copy()
        with patch.object(self.device, 'evaluate', side_effect=lambda xy, base, tools: np.full(len(base), np.nan)):
            with self.assertRaises(Rejected):
                model.update(local_trajectory(1.8)[0])
        np.testing.assert_array_equal(model.vertices, before)
        self.assertFalse(model.tools)
        self.assertFalse(model.attempts[-1]['accepted'])


if __name__ == '__main__':
    unittest.main()
