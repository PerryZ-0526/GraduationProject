"""对拍数值检查与原全量质量口径，包含病态坐标与退化面。"""
import unittest
import numpy as np
from benchmark import quality
from numeric_input import check_and_boxes


class NumericInputTests(unittest.TestCase):
    def test_random_and_degenerate_validity_matches(self):
        rng=np.random.default_rng(2026100602)
        v=rng.normal(size=(200,3));f=rng.integers(0,len(v),size=(4000,3))
        invalid,low,high=check_and_boxes(v,f)
        self.assertEqual(invalid,quality(v,f)['invalid'])
        self.assertTrue(np.array_equal(low,v[f].min(1)));self.assertTrue(np.array_equal(high,v[f].max(1)))

    def test_extreme_numeric_cases_match(self):
        triangles=np.array([[[0,0,0],[1,0,0],[2,0,0]],[[0,0,0],[1e200,0,0],[0,1e-200,0]],[[0,0,0],[1e200,0,0],[1e200,1e-200,0]],[[0,0,0],[1,0,0],[0,np.nan,0]],[[0,0,0],[1,0,0],[0,2e-12,0]],[[0,0,0],[1,0,0],[0,np.nextafter(2e-12,np.inf),0]]])
        v=triangles.reshape(-1,3);f=np.arange(len(v)).reshape(-1,3)
        with np.errstate(all='ignore'):
            for face in f:
                invalid,_,_=check_and_boxes(v,face[None])
                self.assertEqual(invalid,quality(v,face[None])['invalid'])

    def test_safe_range_and_fallback_match_each_precision(self):
        rng=np.random.default_rng(2026100603)
        for dtype,scales in ((np.float64,(1e-200,1e-150,1e-100,1,1e50,1e100,1e152,1e154,1e200)),
                             (np.float32,(1e-30,1e-15,1,1e10,1e17,1e19,1e30))):
            for scale in scales:
                v=(rng.normal(size=(120,3))*scale).astype(dtype)
                f=np.arange(len(v)).reshape(-1,3)
                with np.errstate(all='ignore'):
                    # 逐面核对安全范围与极端回退，不能只比较整个批次的总数。
                    for tri in f:
                        self.assertEqual(check_and_boxes(v,tri[None])[0],quality(v,tri[None])['invalid'])

    def test_extreme_finite_area_keeps_angle_rejection(self):
        for dtype,large,small in ((np.float64,1e200,1e-200),(np.float32,1e30,1e-30)):
            v=np.array([[0,0,0],[large,0,0],[large,small,0]],dtype=dtype)
            f=np.array([[0,1,2]])
            with np.errstate(all='ignore'):
                self.assertEqual(check_and_boxes(v,f)[0],quality(v,f)['invalid'])
                self.assertEqual(check_and_boxes(v,f)[0],1)


if __name__=='__main__':unittest.main()
