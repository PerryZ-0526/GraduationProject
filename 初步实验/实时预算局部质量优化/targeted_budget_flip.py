"""先处理活动区域的小角面，邻接在实际访问时展开，仍保留全局障碍边。"""
import numpy as np
from budget_flip import triangle_metrics
from sparse_budget_flip import ActivityEdges
from resumable_budget_flip import ResumableBudgetFlipState


class LazyActivityEdges(ActivityEdges):
    def __init__(self,faces,active,vertex_count):
        dict.__init__(self)
        self.vertex_count=vertex_count;self.removed=set()
        first=faces.ravel();second=np.roll(faces,-1,axis=1).ravel()
        keys=np.minimum(first,second)*vertex_count+np.maximum(first,second)
        self.order=np.argsort(keys,kind='stable')
        self.sorted_keys=keys[self.order]

    def __getitem__(self,edge):
        if dict.__contains__(self,edge):return dict.__getitem__(self,edge)
        if edge in self.removed:raise KeyError(edge)
        key=edge[0]*self.vertex_count+edge[1]
        left=int(np.searchsorted(self.sorted_keys,key,side='left'))
        right=int(np.searchsorted(self.sorted_keys,key,side='right'))
        if left==right:raise KeyError(edge)
        # 原索引只用于尚未改动的边；动态删除和新增仍由集合与墓碑覆盖。
        owners=set((self.order[left:right]//3).tolist())
        dict.__setitem__(self,edge,owners)
        return owners

    def get(self,edge,default=None):
        try:return self[edge]
        except KeyError:return default

    def setdefault(self,edge,default=None):
        if edge in self:return self[edge]
        self.removed.discard(edge)
        return dict.setdefault(self,edge,default)


class TargetedBudgetFlipState(ResumableBudgetFlipState):
    """小于10度作为工作种子；不是发布硬门槛，原合法网格可直接返回。"""
    edge_factory=LazyActivityEdges

    def _seed_queue(self):
        active_ids=np.flatnonzero(self.active)
        angles,_=triangle_metrics(self.vertices[self.faces[active_ids]])
        seeds=active_ids[angles<10]
        # 优先最小角较差的面；稳定排序使相同输入的初始工作顺序确定。
        order=np.argsort(angles[angles<10],kind='stable')
        self.seed_bad_faces=len(seeds)
        for face_id in seeds[order]:
            tri=self.faces[face_id]
            for k in range(3):self._enqueue(tuple(sorted((int(tri[k]),int(tri[(k+1)%3])))))
