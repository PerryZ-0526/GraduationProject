"""CUDA仅构建全图稳定边索引，质量提交和准确几何保护继续使用CPU规则。"""
import numpy as np
from targeted_budget_flip import LazyActivityEdges,TargetedBudgetFlipState


class CudaActivityEdges(LazyActivityEdges):
    def __init__(self,faces,active,vertex_count):
        import torch
        dict.__init__(self)
        self.vertex_count=vertex_count;self.removed=set()
        # 整数边编码与CPU完全相同；全图远区边仍用于禁止已有新对角线。
        f=torch.as_tensor(np.ascontiguousarray(faces),device='cuda',dtype=torch.int64)
        a=f.reshape(-1);b=torch.roll(f,-1,dims=1).reshape(-1)
        keys=torch.minimum(a,b)*vertex_count+torch.maximum(a,b)
        order=torch.argsort(keys,stable=True)
        # 下载实际索引并同步，两项传输都属于每次构建成本。
        self.order=order.cpu().numpy();self.sorted_keys=keys[order].cpu().numpy()


class CudaPreparedBudgetFlipState(TargetedBudgetFlipState):
    """只更换邻接索引准备，其余候选、评分、几何守卫与提交规则均继承。"""
    edge_factory=CudaActivityEdges
