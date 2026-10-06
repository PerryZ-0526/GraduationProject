"""先限制维护耗时，再以不移动顶点的局部翻边改善小角尾部。"""
from collections import deque
from fractions import Fraction
from time import perf_counter
import numpy as np


def triangle_metrics(points):
    """返回每个三角形的最小角度和面积，输入最后两维为三点三坐标。"""
    angles = []
    for k in range(3):
        u = points[..., (k+1)%3, :] - points[..., k, :]
        v = points[..., (k+2)%3, :] - points[..., k, :]
        lengths = np.linalg.norm(u,axis=-1)*np.linalg.norm(v,axis=-1)
        cosine = np.divide(np.sum(u*v,axis=-1),lengths,out=np.ones_like(lengths),where=lengths>0)
        angles.append(np.degrees(np.arccos(np.clip(cosine,-1,1))))
    area = np.linalg.norm(np.cross(points[...,1,:]-points[...,0,:],points[...,2,:]-points[...,0,:]),axis=-1)/2
    return np.min(angles,axis=0), area


def pair_triangles(quads):
    return quads[:,np.array([[0,1,2],[1,0,3],[2,3,1],[3,2,0]])]


def exact_same_patch(points):
    """用二进制浮点的精确整数表示证明共面、凸性和替换绕序。"""
    ratios = [float(x).as_integer_ratio() for x in points.ravel()]
    denominator = max(d for _,d in ratios)
    p = np.array([n*(denominator//d) for n,d in ratios],dtype=object).reshape(4,3)
    a,b,c,d = p
    u,w,z = b-a,c-a,d-a
    normal = np.array([u[1]*w[2]-u[2]*w[1],u[2]*w[0]-u[0]*w[2],u[0]*w[1]-u[1]*w[0]],dtype=object)
    if not any(normal) or sum(normal*z)!=0:
        return False
    axis = int(np.argmax([abs(int(x)) for x in normal]))
    p = np.delete(p,axis,axis=1)
    def orient(i,j,k):
        v,w = p[j]-p[i],p[k]-p[i]
        return v[0]*w[1]-v[1]*w[0]
    turns = [orient(*tri) for tri in ((0,1,2),(1,0,3),(2,3,1),(3,2,0))]
    return all(x>0 for x in turns) or all(x<0 for x in turns)


class CpuScorer:
    def __init__(self,vertices):
        self.vertices = vertices

    def score(self,quads):
        return triangle_metrics(self.vertices[pair_triangles(quads)])


class TorchScorer:
    """只为有界候选批计算质量；完整传输和同步计入每次评分。"""
    def __init__(self,vertices):
        import torch
        self.torch = torch
        self.vertices = torch.as_tensor(vertices,device='cuda',dtype=torch.float64)
        self.layout = torch.tensor([[0,1,2],[1,0,3],[2,3,1],[3,2,0]],device='cuda')
        self.score(np.array([[0,1,2,3]],dtype=np.int64))

    def score(self,quads):
        t = self.torch
        ids = t.as_tensor(quads,device='cuda',dtype=t.int64)
        p = self.vertices[ids[:,self.layout]]
        angles = []
        for k in range(3):
            u,v = p[...,(k+1)%3,:]-p[...,k,:],p[...,(k+2)%3,:]-p[...,k,:]
            denominator = t.linalg.vector_norm(u,dim=-1)*t.linalg.vector_norm(v,dim=-1)
            cosine = t.where(denominator>0,(u*v).sum(-1)/denominator,t.ones_like(denominator))
            angles.append(t.acos(cosine.clamp(-1,1))*180/np.pi)
        area = t.linalg.vector_norm(t.linalg.cross(p[...,1,:]-p[...,0,:],p[...,2,:]-p[...,0,:],dim=-1),dim=-1)/2
        angle = t.stack(angles).amin(0)
        # 同步下载真实结果，不能用异步发射时间代替GPU完成时间。
        return angle.cpu().numpy(),area.cpu().numpy()


class BudgetFlipState:
    """持久邻接和有界候选队列；新Geogram网格必须重新准备并报告成本。"""
    def __init__(self,vertices,faces,bits,active,backend='cpu',guard_factory=None):
        start = perf_counter()
        self.vertices = np.asarray(vertices,dtype=np.float64).copy()
        self.faces = np.asarray(faces,dtype=np.int64).copy()
        self.bits = np.asarray(bits).copy()
        self.active = np.asarray(active,dtype=bool).copy()
        if len(self.faces)!=len(self.bits) or len(self.active)!=len(self.faces):
            raise ValueError('来源与活动面长度不符')
        if not np.isfinite(self.vertices).all() or np.any(self.faces<0) or np.any(self.faces>=len(self.vertices)):
            raise ValueError('输入坐标或索引非法')
        self.edges = {}
        for i,tri in enumerate(self.faces):
            self._add_face(i,tri)
        self.queue,self.queued = deque(),set()
        for key in self.edges:
            self._enqueue(key)
        self.scorer = CpuScorer(self.vertices) if backend=='cpu' else TorchScorer(self.vertices)
        # 可选近共面守卫必须同时给出误差上界和局部相交检查，不能仅放宽共面容差。
        self.guard = guard_factory(self.vertices,self.faces) if guard_factory else None
        self.preparation_ms = (perf_counter()-start)*1000
        self.backend = backend
        self.sequence = 0

    def _add_face(self,index,tri):
        for k in range(3):
            edge = tuple(sorted((int(tri[k]),int(tri[(k+1)%3]))))
            self.edges.setdefault(edge,set()).add(index)

    def _remove_face(self,index,tri):
        for k in range(3):
            edge = tuple(sorted((int(tri[k]),int(tri[(k+1)%3]))))
            self.edges[edge].remove(index)
            if not self.edges[edge]:del self.edges[edge]

    def _enqueue(self,edge):
        owners = self.edges.get(edge,())
        if edge not in self.queued and len(owners)==2 and all(self.active[i] for i in owners):
            self.queue.append(edge)
            self.queued.add(edge)

    def _candidate(self,edge):
        owners = sorted(self.edges.get(edge,()))
        if len(owners)!=2:return None
        i,j = owners
        if not self.active[i] or not self.active[j] or self.bits[i]!=self.bits[j]:return None
        a,b = edge
        first,second = self.faces[[i,j]]
        if not any(first[k]==a and first[(k+1)%3]==b for k in range(3)):a,b=b,a
        if not any(second[k]==b and second[(k+1)%3]==a for k in range(3)):return None
        c,d = next(int(x) for x in first if x not in edge),next(int(x) for x in second if x not in edge)
        if c==d or tuple(sorted((c,d))) in self.edges:return None
        return i,j,(a,b,c,d)

    def maintain(self,budget_ms=50,max_flips=16):
        """将预算分给多个有界小批，剩余不足一毫秒时不再发起新批。"""
        start=perf_counter();deadline=start+budget_ms/1000;parts=[];accepted=0
        while self.queue and accepted<max_flips:
            remaining=(deadline-perf_counter())*1000
            if remaining<1:break
            row=self.step(remaining,max_candidates=128,max_flips=max_flips-accepted)
            parts.append(row);accepted+=row['accepted']
        elapsed=(perf_counter()-start)*1000
        rejected={name:sum(x['rejected'][name] for x in parts) for name in ('nonplanar_or_nonconvex','quality','stale')}
        return dict(backend=self.backend,budget_ms=budget_ms,elapsed_ms=elapsed,budget_overrun=elapsed>budget_ms,
            visited=sum(x['visited'] for x in parts),scored=sum(x['scored'] for x in parts),accepted=accepted,
            score_ms=sum(x['score_ms'] for x in parts),remaining=len(self.queue),rejected=rejected,
            operations=[op for x in parts for op in x['operations']],micro_batches=len(parts),
            hard_realtime_guaranteed=False,preparation_excluded=True)

    def step(self,budget_ms=5,max_candidates=128,max_flips=16):
        """计时包含取队列、GPU评分同步、精确检查和提交；允许并报告预算越界。"""
        start = perf_counter()
        deadline = start+budget_ms/1000
        visited,accepted,records = 0,0,[]
        rejected = {'nonplanar_or_nonconvex':0,'quality':0,'stale':0}
        batch = []
        while self.queue and visited<max_candidates and perf_counter()<deadline:
            edge = self.queue.popleft();self.queued.remove(edge);visited+=1
            item = self._candidate(edge)
            if item is not None:batch.append(item)
        score_ms = 0
        if batch and perf_counter()<deadline:
            t = perf_counter()
            quads = np.array([x[2] for x in batch])
            angle,area = self.scorer.score(quads)
            score_ms = (perf_counter()-t)*1000
            order = np.argsort(-(angle[:,2:].min(1)-angle[:,:2].min(1)),kind='stable')
            unfinished = list(order)
            for pos,k in enumerate(order):
                if accepted>=max_flips or perf_counter()>=deadline:
                    unfinished = list(order[pos:]);break
                i,j,quad = batch[k]
                edge = tuple(sorted(quad[:2]))
                if self._candidate(edge)!=(i,j,quad):
                    rejected['stale']+=1;continue
                # GPU仅作排序；提交前用同精度CPU复算，不依赖设备分支决定几何有效性。
                angles,areas = triangle_metrics(self.vertices[pair_triangles(np.array([quad]))])
                old,new = angles[0,:2],angles[0,2:]
                old_area,new_area = areas[0,:2],areas[0,2:]
                improves = new.min()>old.min()+1e-8 and np.all(new_area>1e-12)
                for threshold in (10,5,1):
                    improves &= sum(new<threshold)<=sum(old<threshold)
                    improves &= new_area[new<threshold].sum()<=old_area[old<threshold].sum()+1e-12*max(old_area.sum(),1e-30)
                if not improves:
                    rejected['quality']+=1;continue
                proof = self.guard((i,j),quad,deadline) if self.guard else {'exact_same_patch':exact_same_patch(self.vertices[list(quad)]),'error_upper_mm':0.0}
                if not proof.get('accepted',proof.get('exact_same_patch',False)):
                    rejected['nonplanar_or_nonconvex']+=1;continue
                if perf_counter()>=deadline:
                    unfinished = list(order[pos:]);break
                a,b,c,d = quad
                old_faces = self.faces[[i,j]].copy()
                self._remove_face(i,old_faces[0]);self._remove_face(j,old_faces[1])
                self.faces[[i,j]] = [[c,d,b],[d,c,a]]
                self._add_face(i,self.faces[i]);self._add_face(j,self.faces[j])
                if self.guard:self.guard.committed((i,j))
                for tri in self.faces[[i,j]]:
                    for q in range(3):self._enqueue(tuple(sorted((int(tri[q]),int(tri[(q+1)%3])))))
                accepted+=1
                records.append(dict(faces=[i,j],before=old_faces.tolist(),after=self.faces[[i,j]].tolist(),old_min_angle=float(old.min()),new_min_angle=float(new.min()),geometry=proof))
            else:unfinished=[]
            for k in unfinished:self._enqueue(tuple(sorted(batch[k][2][:2])))
        else:
            for item in batch:self._enqueue(tuple(sorted(item[2][:2])))
        self.sequence+=1
        elapsed = (perf_counter()-start)*1000
        return dict(sequence=self.sequence,backend=self.backend,budget_ms=budget_ms,elapsed_ms=elapsed,budget_overrun=elapsed>budget_ms,
            visited=visited,scored=len(batch),accepted=accepted,score_ms=score_ms,remaining=len(self.queue),rejected=rejected,operations=records,
            hard_realtime_guaranteed=False,preparation_excluded=True)
