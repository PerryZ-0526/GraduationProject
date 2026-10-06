"""核对活动邻接不遗漏外部障碍边、边界所有者或动态删除。"""
import unittest
import numpy as np
from budget_flip import BudgetFlipState
from sparse_budget_flip import SparseBudgetFlipState,ActivityEdges
from local_guard import LocalGuard


class SparseBudgetTests(unittest.TestCase):
    def mesh(self):
        return np.array([[0,0,0],[2,1,0],[0,1,0],[1,0,0]],dtype=float),np.array([[0,1,2],[1,0,3]])

    def test_queue_and_flip_match_full(self):
        v,f=self.mesh()
        full=BudgetFlipState(v,f,[1,1],[True,True])
        sparse=SparseBudgetFlipState(v,f,[1,1],[True,True])
        self.assertEqual(list(full.queue),list(sparse.queue))
        self.assertEqual(full.step(100)['accepted'],sparse.step(100)['accepted'])
        self.assertTrue(np.array_equal(full.faces,sparse.faces))
        self.assertNotIn((0,1),sparse.edges)
        self.assertIn((2,3),sparse.edges)
        self.assertEqual({e:owners for e,owners in full.edges.items()},dict(sparse.edges))

    def test_external_diagonal_blocks_flip(self):
        v,f=self.mesh();v=np.vstack((v,[4,0,0]));f=np.vstack((f,[2,3,4]))
        state=SparseBudgetFlipState(v,f,[1,1,1],[True,True,False])
        self.assertIn((2,3),state.edges)
        self.assertNotIn((2,3),dict(state.edges))
        self.assertIsNone(state._candidate((0,1)))
        self.assertEqual(state.step(100)['accepted'],0)

    def test_boundary_keeps_inactive_owner(self):
        v,f=self.mesh();v=np.vstack((v,[0,1,1]));f=np.vstack((f,[2,1,4]))
        state=SparseBudgetFlipState(v,f,[1,1,1],[True,True,False])
        self.assertEqual(state.edges[(1,2)],{0,2})
        self.assertNotIn((1,2),state.queue)
        state.step(100)
        self.assertIn(2,state.edges[(1,2)])
        self.assertTrue(np.array_equal(state.faces[2],f[2]))

    def test_deleted_key_can_be_restored(self):
        _,f=self.mesh();edges=ActivityEdges(f,np.array([True,True]),4)
        del edges[(0,1)];self.assertNotIn((0,1),edges)
        edges.setdefault((0,1),set()).update([0,1])
        self.assertIn((0,1),edges);self.assertEqual(edges[(0,1)],{0,1})

    def test_empty_activity_still_checks_global_membership(self):
        _,f=self.mesh();edges=ActivityEdges(f,np.array([False,False]),4)
        self.assertEqual(len(edges),0)
        self.assertIn((0,1),edges);self.assertNotIn((2,3),edges)

    def test_vectorized_boxes_match_original_reduction(self):
        v=np.random.default_rng(20261006).normal(size=(400,3))
        v[0]=[1e-300,-1e300,0]
        f=np.random.default_rng(20261007).integers(0,len(v),size=(2000,3))
        guard=LocalGuard(v,f)
        self.assertTrue(np.array_equal(guard.low,v[f].min(1)))
        self.assertTrue(np.array_equal(guard.high,v[f].max(1)))


if __name__=='__main__':unittest.main()
