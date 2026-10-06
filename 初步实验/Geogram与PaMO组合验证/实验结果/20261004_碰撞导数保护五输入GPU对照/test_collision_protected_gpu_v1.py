"""在实际CUDA上测试新增固定点策略，不以模拟测试替代完整网格对照。"""
from types import SimpleNamespace
import unittest
import numpy as np
import warp as wp
from collision_protected_gpu import CollisionProtectedSystem


@wp.kernel
def add_terms(source_g:wp.array(dtype=wp.vec3),source_d:wp.array(dtype=wp.vec3),
              gradient:wp.array(dtype=wp.vec3),diagonal:wp.array(dtype=wp.vec3)):
    i=wp.tid()
    gradient[i]=gradient[i]+source_g[i]
    diagonal[i]=diagonal[i]+source_d[i]


class Terms:
    def __init__(self,bad_g=(),bad_d=()):
        g=np.tile([1.,0.,0.],(4,1));d=np.ones((4,3))
        g[list(bad_g)]=np.nan;d[list(bad_d)]=np.nan
        self.g=wp.array(g,dtype=wp.vec3,device="cuda:0")
        self.d=wp.array(d,dtype=wp.vec3,device="cuda:0")

    def compute_diff(self,q,coeff,g,d):
        wp.launch(add_terms,dim=4,inputs=[self.g,self.d],outputs=[g,d],device="cuda:0")


class DistanceTest(Terms):
    pass


class CollisionTest(Terms):
    pass


def fixture(collision_g=(),collision_d=(),distance_g=()):
    # 跳过大容量场景注册，只用真实CUDA数组测试同一求导/掩码实现。
    s=CollisionProtectedSystem.__new__(CollisionProtectedSystem)
    s.device="cuda:0";s.n_particles=4
    s.grad=wp.zeros(4,dtype=wp.vec3,device=s.device)
    s.hess_diag=wp.zeros(4,dtype=wp.vec3,device=s.device)
    s.q=wp.array(np.ones((4,3)),dtype=wp.vec3,device=s.device)
    s.support_normals=wp.array(np.tile([0.,0.,1.],(4,1)),dtype=wp.vec3,device=s.device)
    s.fixed_host=np.array([False,False,False,True])
    s.set_fixed(s.fixed_host)
    s.protected_vertices=[];s.protection_records=[];s.diff_calls=0
    s.config=SimpleNamespace(energy_calcs=[DistanceTest,CollisionTest])
    s.energy_calcs={DistanceTest:DistanceTest(distance_g),CollisionTest:CollisionTest(collision_g,collision_d)}
    return s


class ProtectionTests(unittest.TestCase):
    def test_finite_terms_unchanged(self):
        s=fixture();s._compute_diff();self.assertEqual(s.protected_vertices,[])

    def test_collision_gradient_protected(self):
        s=fixture(collision_g=(0,));s._compute_diff();self.assertEqual(s.protected_vertices,[0])
        self.assertTrue(np.isfinite(s.grad.numpy()).all())

    def test_collision_diagonal_protected(self):
        s=fixture(collision_d=(1,));s._compute_diff();self.assertEqual(s.protected_vertices,[1])

    def test_noncollision_bad_rejected(self):
        s=fixture(collision_g=(0,),distance_g=(2,))
        with self.assertRaises(RuntimeError):s._compute_diff()
        self.assertEqual(s.protected_vertices,[])

    def test_later_failure_rejected(self):
        s=fixture(collision_g=(0,));s.diff_calls=1
        with self.assertRaises(RuntimeError):s._compute_diff()

    def test_nonfinite_position_rejected(self):
        s=fixture(collision_g=(0,));s.q.assign(np.full((4,3),np.nan))
        with self.assertRaises(RuntimeError):s._compute_diff()

    def test_already_fixed_bad_not_added(self):
        s=fixture(collision_g=(3,),collision_d=(3,));s._compute_diff();self.assertEqual(s.protected_vertices,[])


if __name__=="__main__":
    unittest.main()
