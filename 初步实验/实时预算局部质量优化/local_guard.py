"""近共面翻边的有理数距离上界与静态局部相交守卫，不改坐标。"""
from fractions import Fraction
from math import sqrt,nextafter,inf
from time import perf_counter
import numpy as np


def integer_points(vertices):
    ratios=[float(x).as_integer_ratio() for x in vertices.ravel()]
    denominator=max(d for _,d in ratios)
    return np.array([n*(denominator//d) for n,d in ratios],dtype=object).reshape(-1,3),denominator


def cross(a,b):
    return np.array([a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]],dtype=object)


def dot(a,b):return sum(a*b)


def plane_bound(vertices,tolerance_mm):
    """原两面与新两面均映到相同凸平面四边形，双向距离至多两倍高度。"""
    p,denominator=integer_points(vertices)
    a,b,c,d=p
    normals=[cross(b-a,c-a),cross(b-a,d-a)]
    normal=max(normals,key=lambda n:dot(n,n));norm2=dot(normal,normal)
    if not norm2:return None
    heights=[dot(normal,x-a) for x in p]
    height2=Fraction(max(x*x for x in heights),norm2*denominator*denominator)
    if 4*height2>Fraction.from_float(tolerance_mm)**2:return None
    # 正交投影乘共同整数分母，随后用精确二维绕序验证共同像为凸四边形。
    projected=np.array([x*norm2-normal*h for x,h in zip(p,heights)],dtype=object)
    axis=int(np.argmax([abs(int(x)) for x in normal]));q=np.delete(projected,axis,axis=1)
    def orient(i,j,k):
        u,v=q[j]-q[i],q[k]-q[i];return u[0]*v[1]-u[1]*v[0]
    turns=[orient(*x) for x in ((0,1,2),(1,0,3),(2,3,1),(3,2,0))]
    if not(all(x>0 for x in turns) or all(x<0 for x in turns)):return None
    upper=nextafter(2*sqrt(float(height2)),inf) if height2 else 0.0
    while Fraction.from_float(upper)**2<4*height2:upper=nextafter(upper,inf)
    return dict(error_upper_mm=upper,height_squared_numerator=str(height2.numerator),height_squared_denominator=str(height2.denominator),exact_same_patch=height2==0)


def separated_except_shared(vertices,first,second,deadline):
    """精确投影区间证明两三角形分离，或仅共享声明的顶点/边。"""
    ids=sorted(set(first)|set(second));index={v:i for i,v in enumerate(ids)}
    p,_=integer_points(vertices[ids]);a=p[[index[x] for x in first]];b=p[[index[x] for x in second]]
    shared=set(first)&set(second)
    if len(shared)==3:return False
    ae=[a[(k+1)%3]-a[k] for k in range(3)];be=[b[(k+1)%3]-b[k] for k in range(3)]
    an,bn=cross(ae[0],ae[1]),cross(be[0],be[1])
    axes=[an,bn]+[cross(x,y) for x in ae for y in be]+[cross(an,x) for x in ae]+[cross(bn,x) for x in be]
    for axis in axes:
        if perf_counter()>=deadline:return False
        if not any(axis):continue
        av,bv=[dot(x,axis) for x in a],[dot(x,axis) for x in b]
        for values,other,owners,other_owners in ((av,bv,first,second),(bv,av,second,first)):
            high,low=max(values),min(other)
            if high<low:return True
            if high==low and shared:
                support={owners[k] for k in range(3) if values[k]==high}
                other_support={other_owners[k] for k in range(3) if other[k]==low}
                # 接触支撑面只有原共同实体时，交集不会超出合法顶点或边。
                if support<=shared or other_support<=shared:return True
    return False


class LocalGuard:
    """全网格包围盒初始化单列；检查新面与所有包围盒重叠面的实际关系。"""
    # 原生版本只替换精确分离判定，距离上界、全域障碍和提交规则共同继承。
    separation_check=staticmethod(separated_except_shared)
    def __init__(self,vertices,faces,tolerance_mm=1e-10):
        self.vertices,self.faces,self.tolerance=vertices,faces,tolerance_mm
        # 三点逐分量取极值与原归约逐位一致，减少全网格短轴归约的准备成本。
        a,b,c=(vertices[faces[:,k]] for k in range(3))
        self.low=np.minimum(np.minimum(a,b),c)
        self.high=np.maximum(np.maximum(a,b),c)

    def committed(self,ids):
        triangles=self.vertices[self.faces[list(ids)]]
        self.low[list(ids)]=triangles.min(1);self.high[list(ids)]=triangles.max(1)

    def __call__(self,owners,quad,deadline):
        proof=plane_bound(self.vertices[list(quad)],self.tolerance)
        if proof is None:return dict(accepted=False,reason='几何上界或凸性不符')
        a,b,c,d=quad;new_faces=[[c,d,b],[d,c,a]];checks=0
        for tri in new_faces:
            points=self.vertices[tri]
            # 顶点不移动，逐分量比较与原三轴归约完全相同，避免全网格短轴归约的额外开销。
            # 仍查全部盒子，不用近似距离截掉接触或删除外部障碍。
            low,high=points.min(0),points.max(0)
            overlap=np.flatnonzero((self.high[:,0]>=low[0])&(self.high[:,1]>=low[1])&(self.high[:,2]>=low[2])&
                (self.low[:,0]<=high[0])&(self.low[:,1]<=high[1])&(self.low[:,2]<=high[2]))
            for face_id in overlap:
                if face_id in owners:continue
                if perf_counter()>=deadline:return dict(accepted=False,reason='守卫预算耗尽')
                checks+=1
                # 子类替换实现也必须保留相同的共享实体支撑与超时语义。
                if not self.separation_check(self.vertices,tri,list(self.faces[face_id]),deadline):
                    return dict(accepted=False,reason='无法证明局部分离',checks=checks)
        proof.update(accepted=True,local_separation_checks=checks,static_only=True)
        return proof
