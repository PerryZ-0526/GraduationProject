"""独立梯度参照的有限差分、刚体不变量与无定义范围验证。"""
import unittest
import numpy as np
from pt_exact_reference import point_triangle_reference
from pt_gradient_reference import point_triangle_gradient


class PointTriangleGradientTests(unittest.TestCase):
    def test_all_features_by_finite_difference(self):
        triangle=np.array([[0,0,0],[1,0,0],[0,1,0]])
        for point in [[.25,.25,.5],[-1,-1,.2],[2,0,.2],[.5,-.2,.1],[0,2,.2],[-.2,.5,.1],[.6,.6,.1]]:
            values=np.vstack([point,triangle])
            expected=point_triangle_gradient(values)
            differences=np.zeros((4,3))
            for i in range(4):
                for j in range(3):
                    plus,minus=values.copy(),values.copy()
                    plus[i,j]+=1e-6
                    minus[i,j]-=1e-6
                    differences[i,j]=(point_triangle_reference(plus)[1]-point_triangle_reference(minus)[1])/2e-6
            self.assertLess(np.max(np.abs(expected-differences)),1e-7)

    def test_translation_and_rotation(self):
        values=np.array([[.25,.25,.5],[0,0,0],[1,0,0],[0,1,0]])
        rotation=np.array([[0,-1,0],[1,0,0],[0,0,1]])
        gradient=point_triangle_gradient(values)
        self.assertLess(np.max(np.abs(gradient.sum(axis=0))),1e-14)
        self.assertTrue(np.allclose(point_triangle_gradient(values@rotation.T+[2,3,4]),gradient@rotation.T,atol=1e-14,rtol=0))

    def test_zero_distance_rejected(self):
        with self.assertRaisesRegex(ValueError,"零距离"):
            point_triangle_gradient([[.25,.25,0],[0,0,0],[1,0,0],[0,1,0]])

    def test_degenerate_rejected(self):
        with self.assertRaisesRegex(ValueError,"退化"):
            point_triangle_gradient([[.5,.1,0],[0,0,0],[1,0,0],[.5,0,0]])


if __name__=="__main__":
    unittest.main()
