"""向量化保留全局边存在性，只将活动区域邻接展开为可修改集合。"""
from collections import deque
from time import perf_counter
import numpy as np
from budget_flip import BudgetFlipState,CpuScorer,TorchScorer


class ActivityEdges(dict):
    """外部边仍参与新对角线检查；局部删除用墓碑覆盖初始索引。"""
    def __init__(self,faces,active,vertex_count):
        super().__init__()
        self.vertex_count=vertex_count
        self.removed=set()
        # 直接比较两个端点，避免为短轴归约创建三维临时数组。
        first=faces.ravel();second=np.roll(faces,-1,axis=1).ravel()
        keys=np.minimum(first,second)*vertex_count+np.maximum(first,second)
        order=np.argsort(keys,kind='stable')
        self.sorted_keys=keys[order]
        local=np.unique(keys[np.repeat(active,3)])
        left=np.searchsorted(self.sorted_keys,local,side='left')
        right=np.searchsorted(self.sorted_keys,local,side='right')
        # 保持原逐面插入的队列次序，避免把排序变化混入准备机制对照。
        for pos in np.argsort(order[left],kind='stable'):
            key=int(local[pos]);edge=divmod(key,vertex_count)
            self[edge]=set((order[left[pos]:right[pos]]//3).tolist())

    def __contains__(self,edge):
        if dict.__contains__(self,edge):return True
        if edge in self.removed:return False
        key=edge[0]*self.vertex_count+edge[1]
        pos=int(np.searchsorted(self.sorted_keys,key))
        return pos<len(self.sorted_keys) and self.sorted_keys[pos]==key

    def __delitem__(self,edge):
        dict.__delitem__(self,edge)
        self.removed.add(edge)

    def setdefault(self,edge,default=None):
        self.removed.discard(edge)
        return dict.setdefault(self,edge,default)


class SparseBudgetFlipState(BudgetFlipState):
    """复用原质量、相交守卫及提交规则；仅替换邻接准备。"""
    edge_factory=ActivityEdges
    def __init__(self,vertices,faces,bits,active,backend='cpu',guard_factory=None):
        start=perf_counter()
        self.vertices=np.asarray(vertices,dtype=np.float64).copy()
        self.faces=np.asarray(faces,dtype=np.int64).copy()
        self.bits=np.asarray(bits).copy()
        self.active=np.asarray(active,dtype=bool).copy()
        if len(self.faces)!=len(self.bits) or len(self.active)!=len(self.faces):
            raise ValueError('来源与活动面长度不符')
        if not np.isfinite(self.vertices).all() or np.any(self.faces<0) or np.any(self.faces>=len(self.vertices)):
            raise ValueError('输入坐标或索引非法')
        if len(self.vertices)**2>np.iinfo(np.int64).max:
            raise ValueError('边编码超出整数范围')
        # 边索引与初始候选可由受约束子类替换，提交与几何规则仍复用同一实现。
        self.edges=self.edge_factory(self.faces,self.active,len(self.vertices))
        self.queue,self.queued=deque(),set()
        self._seed_queue()
        self.scorer=CpuScorer(self.vertices) if backend=='cpu' else TorchScorer(self.vertices)
        self.guard=guard_factory(self.vertices,self.faces) if guard_factory else None
        self.preparation_ms=(perf_counter()-start)*1000
        self.backend=backend
        self.sequence=0

    def _seed_queue(self):
        for edge in self.edges:self._enqueue(edge)
