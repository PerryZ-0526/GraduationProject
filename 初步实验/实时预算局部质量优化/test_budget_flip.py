"""验证预算翻边的几何不变性、来源锁定和可继续工作语义。"""
import unittest
import numpy as np
from budget_flip import BudgetFlipState,exact_same_patch
from local_guard import plane_bound,LocalGuard,separated_except_shared
from fractions import Fraction
from time import perf_counter


class BudgetFlipTests(unittest.TestCase):
    def mesh(self):
        v=np.array([[0,0,0],[2,1,0],[0,1,0],[1,0,0]],dtype=float)
        return v,np.array([[0,1,2],[1,0,3]])

    def test_exact_plane_rejects_tiny_offset(self):
        v,_=self.mesh();self.assertTrue(exact_same_patch(v))
        v[3,2]=1e-16;self.assertFalse(exact_same_patch(v))

    def test_flip_preserves_vertices_and_tail(self):
        v,f=self.mesh();s=BudgetFlipState(v,f,[1,1],[True,True])
        r=s.step(100);self.assertEqual(r['accepted'],1)
        self.assertTrue(np.array_equal(s.vertices,v));self.assertTrue(r['operations'][0]['new_min_angle']>r['operations'][0]['old_min_angle'])
        self.assertEqual(sum(map(len,s.edges.values())),6)

    def test_external_and_source_locks(self):
        v,f=self.mesh()
        for bits,active in (([1,2],[True,True]),([1,1],[True,False])):
            s=BudgetFlipState(v,f,bits,active);s.step(100)
            self.assertTrue(np.array_equal(s.faces,f))

    def test_zero_budget_can_resume(self):
        v,f=self.mesh();s=BudgetFlipState(v,f,[1,1],[True,True])
        r=s.step(0);self.assertEqual(r['accepted'],0);self.assertGreater(r['remaining'],0)
        self.assertEqual(s.step(100)['accepted'],1)

    def test_nonconvex_rejected(self):
        v,_=self.mesh();v[3]=[0.2,0.8,0]
        self.assertFalse(exact_same_patch(v))

    def test_near_plane_has_exact_height_bound(self):
        v,_=self.mesh();v[3,2]=1e-16
        proof=plane_bound(v,1e-10);self.assertIsNotNone(proof)
        h=Fraction(int(proof['height_squared_numerator']),int(proof['height_squared_denominator']))
        self.assertGreaterEqual(Fraction.from_float(proof['error_upper_mm'])**2,4*h)
        v[3,2]=0.1;self.assertIsNone(plane_bound(v,1e-10))

    def test_crossing_face_blocks_flip(self):
        v,f=self.mesh();v=np.vstack([v,[[0.5,0.5,-1],[0.5,0.5,1],[1,0.5,0]]])
        f=np.vstack([f,[4,5,6]])
        guard=LocalGuard(v,f)
        self.assertFalse(guard((0,1),(0,1,2,3),perf_counter()+1)['accepted'])

    def test_shared_edge_and_disjoint_faces(self):
        v,_=self.mesh();v=np.vstack([v,[[0,1,1],[3,0,0],[4,0,0],[3,1,0]]])
        self.assertTrue(separated_except_shared(v,[0,1,2],[1,0,4],perf_counter()+1))
        self.assertTrue(separated_except_shared(v,[0,1,2],[5,6,7],perf_counter()+1))

    def test_near_guard_respects_budget(self):
        v,f=self.mesh();v[3,2]=1e-16
        s=BudgetFlipState(v,f,[1,1],[True,True],guard_factory=LocalGuard)
        self.assertEqual(s.step(100)['accepted'],1)

    def test_multi_batch_operation_limit(self):
        v,f=self.mesh();s=BudgetFlipState(v,f,[1,1],[True,True])
        self.assertEqual(s.maintain(100,max_flips=1)['accepted'],1)
        self.assertEqual(s.maintain(0)['accepted'],0)


if __name__=='__main__':unittest.main()
