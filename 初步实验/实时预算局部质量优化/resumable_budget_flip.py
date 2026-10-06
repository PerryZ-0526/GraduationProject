"""预算中断的守卫候选返回队列，避免将时间不足当作永久几何拒绝。"""
from time import perf_counter
from sparse_budget_flip import SparseBudgetFlipState


class ResumableGuard:
    def __init__(self,guard):
        self.guard=guard
        self.deferred=[]
        self.total_deferred=0

    def __call__(self,owners,quad,deadline):
        proof=self.guard(owners,quad,deadline)
        if not proof.get('accepted',False) and perf_counter()>=deadline:
            self.deferred.append(tuple(sorted(quad[:2])))
            self.total_deferred+=1
        return proof

    def committed(self,owners):self.guard.committed(owners)


class ResumableBudgetFlipState(SparseBudgetFlipState):
    """原几何条件保持；只有超时未完成候选获得下次继续机会。"""
    def __init__(self,vertices,faces,bits,active,backend='cpu',guard_factory=None):
        wrapped=(lambda v,f:ResumableGuard(guard_factory(v,f))) if guard_factory else None
        super().__init__(vertices,faces,bits,active,backend,wrapped)

    def step(self,budget_ms=5,max_candidates=128,max_flips=16):
        start=perf_counter()
        if self.guard:self.guard.deferred.clear()
        result=super().step(budget_ms,max_candidates,max_flips)
        deferred=self.guard.deferred if self.guard else []
        for edge in deferred:self._enqueue(edge)
        result['rejected']['nonplanar_or_nonconvex']-=len(deferred)
        result['deferred_by_budget']=len(deferred)
        result['remaining']=len(self.queue)
        # 队列恢复也属于实际执行成本，不从计时中删掉。
        result['elapsed_ms']=(perf_counter()-start)*1000
        result['budget_overrun']=result['elapsed_ms']>budget_ms
        return result

    def maintain(self,budget_ms=50,max_flips=16):
        previous=self.guard.total_deferred if self.guard else 0
        result=super().maintain(budget_ms,max_flips)
        result['deferred_by_budget']=(self.guard.total_deferred-previous) if self.guard else 0
        return result
