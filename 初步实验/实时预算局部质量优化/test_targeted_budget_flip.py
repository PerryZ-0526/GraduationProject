"""核对按需邻接、外部对角线、变化边覆盖和小角种子的工作语义。"""
import unittest
import numpy as np
from sparse_budget_flip import SparseBudgetFlipState
from targeted_budget_flip import TargetedBudgetFlipState,LazyActivityEdges


class TargetedBudgetTests(unittest.TestCase):
    def mesh(self):
        return np.array([[0,0,0],[2,.1,0],[0,.1,0],[1,0,0]],dtype=float),np.array([[0,1,2],[1,0,3]])

    def test_bad_faces_seed_flip(self):
        v,f=self.mesh();state=TargetedBudgetFlipState(v,f,[1,1],[True,True])
        self.assertEqual(state.seed_bad_faces,2)
        self.assertEqual(state.step(100)['accepted'],1)
        self.assertNotIn((0,1),state.edges);self.assertIn((2,3),state.edges)
        full=SparseBudgetFlipState(v,f,[1,1],[True,True]);full.step(100)
        self.assertTrue(np.array_equal(full.faces,state.faces))

    def test_quality_above_seed_does_not_force_work(self):
        v,f=self.mesh();v[1,1]=1;v[2,1]=1
        state=TargetedBudgetFlipState(v,f,[1,1],[True,True])
        self.assertEqual(state.seed_bad_faces,0);self.assertEqual(state.step(100)['accepted'],0)
        self.assertEqual(len(state.edges),0)

    def test_external_diagonal_preserved(self):
        v,f=self.mesh();v=np.vstack([v,[4,0,0]]);f=np.vstack([f,[2,3,4]])
        state=TargetedBudgetFlipState(v,f,[1,1,1],[True,True,False])
        self.assertIn((2,3),state.edges);self.assertIsNone(state._candidate((0,1)))
        self.assertEqual(state.step(100)['accepted'],0)

    def test_lazy_boundary_owner_and_restore(self):
        _,f=self.mesh();f=np.vstack([f,[2,1,4]])
        edges=LazyActivityEdges(f,np.array([True,True,False]),5)
        self.assertEqual(edges[(1,2)],{0,2})
        self.assertEqual(edges.setdefault((1,2),set()),{0,2})
        self.assertEqual(edges[(0,1)],{0,1});del edges[(0,1)]
        self.assertNotIn((0,1),edges);self.assertIsNone(edges.get((0,1)))
        edges.setdefault((0,1),set()).add(3)
        self.assertEqual(edges[(0,1)],{3})


if __name__=='__main__':unittest.main()
