"""冻结138段恢复与物理路径保持；不让失败后的未执行段变成成功。"""
import unittest
from collections import Counter
import numpy as np
from coverage_inputs import original_plan


class CoverageTests(unittest.TestCase):
    def test_original_plan(self):
        plan=original_plan()
        self.assertEqual(len(plan),138)
        self.assertEqual(len(Counter(t['phase'] for t in plan)),5)
        self.assertTrue(all(t['clip_radius']>0 for t in plan))
        self.assertTrue(any(t['start'][2]!=t['end'][2] for t in plan))

    def test_physical_resampling(self):
        from incremental import cpu_sweep
        from coverage_inputs import variant_trajectories
        cases=variant_trajectories()
        rng=np.random.default_rng(20260908)
        xy=rng.uniform(-4,4,(4096,2))
        outputs=[]
        for name in ['control','fine_32','coarse_8']:
            tools=np.array([[*t.start,*t.end,t.radius,t.z] for t in cases[name]])
            outputs.append(cpu_sweep(xy,np.zeros(len(xy)),tools))
        for value in outputs[1:]:
            np.testing.assert_allclose(value,outputs[0],rtol=0,atol=1e-12)


if __name__=='__main__':
    unittest.main()
