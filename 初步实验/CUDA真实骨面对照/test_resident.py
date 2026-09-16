"""真实CUDA增量驻留、历史回退与审计故障注入。"""
import unittest
from unittest.mock import patch
import numpy as np
from cuda_device import CheckedGpuPatch, cpu_sweep
from resident_device import ResidentDevice
from incremental import PrefixSweep
from experiment import load_candidate
from real_patch import local_trajectory
from integrated import Rejected


class ResidentTests(unittest.TestCase):
    def test_prefix_branch_and_eviction(self):
        rng = np.random.default_rng(20260908)
        xy, base = rng.uniform(-4, 4, (3000, 2)), np.full(3000, 2.)
        tools = np.array([[0., 0., .02*i, .1, 3., 1.8] for i in range(16)])
        for budget in [1, 128*1024*1024]:
            device = ResidentDevice(budget)
            for history in [tools[:1], tools[:8], tools, tools, tools[:4], tools[::-1], tools[:0]]:
                np.testing.assert_allclose(device.evaluate(xy, base, history), cpu_sweep(xy, base, history), rtol=0, atol=1e-10)
            changed = base.copy()
            changed[0] = -9
            np.testing.assert_allclose(device.evaluate(xy, changed, tools), cpu_sweep(xy, changed, tools), rtol=0, atol=1e-10)
            self.assertLessEqual(device.cache_bytes, budget)

    def test_corruption_rejected_after_cached_step(self):
        candidate, chart = load_candidate()
        device, reference = ResidentDevice(), PrefixSweep(cpu_sweep)
        model = CheckedGpuPatch(chart, candidate, device, reference=reference.evaluate)
        model.update(local_trajectory(1.8)[0])
        before, history = model.vertices.copy(), list(model.tools)
        actual = device.evaluate
        with patch.object(device, 'evaluate', side_effect=lambda *args: actual(*args)+1e-3):
            with self.assertRaises(Rejected):
                model.update(local_trajectory(1.8)[1])
        np.testing.assert_array_equal(before, model.vertices)
        self.assertEqual(model.tools, history)
        model.update(local_trajectory(1.8)[1])
        self.assertTrue(model.attempts[-1]['accepted'])


if __name__ == '__main__':
    unittest.main()
