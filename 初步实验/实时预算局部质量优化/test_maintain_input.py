"""核对数组适配、共享包围盒和无效源拒绝，不把数值核查当作全量嵌入。"""
import unittest
import numpy as np
from local_guard import LocalGuard
from maintain_input import maintain_input


class MaintainInputTests(unittest.TestCase):
    def test_shared_boxes_match_after_commit(self):
        v=np.array([[0,0,0],[2,.1,0],[0,.1,0],[1,0,0]],dtype=float)
        f=np.array([[0,1,2],[1,0,3]])
        state,row=maintain_input(v,f,np.array([1,1]),np.array([-1,-1,-1]),np.array([3,3,3]),200)
        self.assertEqual(row['accepted'],1)
        expected=LocalGuard(state.vertices,state.faces)
        self.assertTrue(np.array_equal(expected.low,state.guard.guard.low))
        self.assertTrue(np.array_equal(expected.high,state.guard.guard.high))
        self.assertTrue(np.array_equal(state.vertices,v))

    def test_invalid_source_refused(self):
        v=np.array([[0,0,0],[1,0,0],[2,0,0]],dtype=float)
        with self.assertRaises(ValueError):
            maintain_input(v,np.array([[0,1,2]]),np.array([1]),np.zeros(3),np.ones(3),50)


if __name__=='__main__':unittest.main()
