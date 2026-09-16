"""增量复用必须与完整历史计算一致，失效、淘汰和分支不得污染结果。"""
import unittest
import numpy as np
from incremental import PrefixSweep, cpu_sweep


class PrefixTests(unittest.TestCase):
    def test_batching_keeps_certificate_samples(self):
        from patch_model import PatchModel, Sweep
        models=[]
        for batch in [1,64,512]:
            model=PatchModel(.2)
            model.query_batch_faces=batch
            model.update(Sweep((-.5,.07),(.5,.07),2.,1.6))
            models.append(model)
        for model in models[1:]:
            np.testing.assert_array_equal(model.vertices,models[0].vertices)
            np.testing.assert_array_equal(model.bounds,models[0].bounds)
            self.assertEqual(model.attempts[-1]['queries'],models[0].attempts[-1]['queries'])

    def test_history_and_query_changes(self):
        rng = np.random.default_rng(20260908)
        xy = rng.uniform(-4, 4, (1000, 2))
        base = np.full(1000, 2.)
        tools = np.array([[0., 0., i*.03, .1, 3., 1.8] for i in range(12)])
        cache = PrefixSweep(cpu_sweep)
        for history in [tools[:1], tools[:7], tools, tools, tools[:3], tools[::-1], tools[:0]]:
            np.testing.assert_array_equal(cache.evaluate(xy, base, history), cpu_sweep(xy, base, history))
        changed = base.copy()
        changed[0] -= 2
        for points, heights in [(xy, changed), (xy[::-1], base), (xy[:0], base[:0])]:
            np.testing.assert_array_equal(cache.evaluate(points, heights, tools), cpu_sweep(points, heights, tools))

    def test_reuse_and_eviction(self):
        xy, base = np.zeros((4, 2)), np.zeros(4)
        tools = np.array([[0., 0., 0., 0., 3., 1.8]]*3)
        cache = PrefixSweep(cpu_sweep)
        cache.evaluate(xy, base, tools[:2])
        result = cache.evaluate(xy, base, tools)
        self.assertEqual(cache.reused_pairs, 8)
        result[:] = 999
        np.testing.assert_array_equal(cache.evaluate(xy, base, tools), cpu_sweep(xy, base, tools))
        small = PrefixSweep(cpu_sweep, budget=1)
        small.evaluate(xy, base, tools)
        self.assertEqual(small.bytes, 0)


if __name__ == '__main__':
    unittest.main()
