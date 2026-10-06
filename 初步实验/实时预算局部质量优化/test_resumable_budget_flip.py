"""复现守卫耗尽预算后丢失候选的问题，并核对下次可继续。"""
import unittest
from time import perf_counter
import numpy as np
from resumable_budget_flip import ResumableBudgetFlipState


class InterruptedGuard:
    def __init__(self,vertices,faces):self.first=True
    def committed(self,owners):pass
    def __call__(self,owners,quad,deadline):
        if self.first:
            self.first=False
            while perf_counter()<=deadline:pass
            return dict(accepted=False,reason='测试预算中断')
        return dict(accepted=True,exact_same_patch=True,error_upper_mm=0.0)


class ResumableBudgetTests(unittest.TestCase):
    def test_interrupted_guard_candidate_can_resume(self):
        v=np.array([[0,0,0],[2,1,0],[0,1,0],[1,0,0]],dtype=float)
        f=np.array([[0,1,2],[1,0,3]])
        state=ResumableBudgetFlipState(v,f,[1,1],[True,True],guard_factory=InterruptedGuard)
        first=state.step(100)
        self.assertEqual(first['accepted'],0)
        self.assertEqual(first['deferred_by_budget'],1)
        self.assertEqual(first['rejected']['nonplanar_or_nonconvex'],0)
        self.assertEqual(list(state.queue),[(0,1)])
        self.assertTrue(np.array_equal(state.faces,f))
        second=state.step(100)
        self.assertEqual(second['accepted'],1)
        self.assertEqual(second['deferred_by_budget'],0)


if __name__=='__main__':unittest.main()
