"""读取同源精确父证书的全局邻接，局部改动通过原集合和墓碑覆盖。"""
import ctypes as C
import numpy as np
from incremental_mesh_memory import VerifiedMesh
from sparse_budget_flip import ActivityEdges
from targeted_budget_flip import TargetedBudgetFlipState


class SharedVerifiedMesh(VerifiedMesh):
    def __init__(self):
        self.revision=0
        super().__init__()
        p=C.c_void_p;n=C.c_uint64
        self.lib.bind_quality_topology.argtypes=[p,p,n,p,n]
        self.lib.bind_quality_topology.restype=C.c_int
        self.lib.quality_edge_owners.argtypes=[p,C.c_int64,C.c_int64,p]
        self.lib.quality_edge_owners.restype=C.c_int

    def close(self):
        # Python顺序调用下，关闭或更换证书后旧视图必须在接触原生指针前拒绝。
        self.revision+=1
        super().close()

    def check_flips(self,vertices,faces,operations):
        result=super().check_flips(vertices,faces,operations)
        if result['advanced']:self.revision+=1
        return result

    def quality_view(self,vertices,faces):
        v=np.ascontiguousarray(vertices,dtype=np.float64)
        f=np.ascontiguousarray(faces,dtype=np.int64)
        if v.ndim!=2 or v.shape[1]!=3 or f.ndim!=2 or f.shape[1]!=3:raise ValueError('邻接复用数组形状错误')
        if not self.handle:raise ValueError('邻接复用缺少实际父证书')
        code=self.lib.bind_quality_topology(self.handle,v.ctypes.data,len(v),f.ctypes.data,len(f))
        if code:raise ValueError('邻接复用的坐标或有向面与实际父证书不一致')
        return QualityTopologyView(self)


class QualityTopologyView:
    def __init__(self,certificate):
        self.certificate=certificate
        self.handle=certificate.handle;self.revision=certificate.revision
        self.output=(C.c_int64*2)()

    def ensure_current(self):
        # 成功提交翻边也使旧视图过期；不能用变化后的父图解释之前的动态覆盖层。
        if self.certificate.handle!=self.handle or self.certificate.revision!=self.revision:
            raise ValueError('质量邻接视图已过期')

    def owners(self,edge):
        self.ensure_current()
        count=self.certificate.lib.quality_edge_owners(self.handle,*edge,self.output)
        if count<0:raise ValueError('质量邻接查询编号非法')
        return set(self.output) if count==2 else None


class CertificateActivityEdges(ActivityEdges):
    def __init__(self,view):
        dict.__init__(self)
        self.view=view;self.removed=set()

    def __getitem__(self,edge):
        self.view.ensure_current()
        if dict.__contains__(self,edge):return dict.__getitem__(self,edge)
        if edge in self.removed:raise KeyError(edge)
        owners=self.view.owners(edge)
        if owners is None:raise KeyError(edge)
        dict.__setitem__(self,edge,owners)
        return owners

    def __contains__(self,edge):
        self.view.ensure_current()
        if dict.__contains__(self,edge):return True
        if edge in self.removed:return False
        return self.view.owners(edge) is not None

    def get(self,edge,default=None):
        try:return self[edge]
        except KeyError:return default

    def setdefault(self,edge,default=None):
        if edge in self:return self[edge]
        self.removed.discard(edge)
        return dict.setdefault(self,edge,default)


class CertificateBudgetFlipState(TargetedBudgetFlipState):
    def __init__(self,vertices,faces,bits,active,backend,guard_factory,certificate):
        # 同源绑定、所有查询及覆盖集合成本仍包含在调用方维护计时中。
        self.edge_factory=lambda f,a,n:CertificateActivityEdges(certificate.quality_view(vertices,f))
        super().__init__(vertices,faces,bits,active,backend,guard_factory)
