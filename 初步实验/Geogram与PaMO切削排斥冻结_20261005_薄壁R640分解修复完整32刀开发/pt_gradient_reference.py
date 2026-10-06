"""固定FP32坐标最近实体的有理数权重梯度参照，不解释零距离导数。"""
from fractions import Fraction
import numpy as np
from pt_exact_reference import point_triangle_reference


def point_triangle_gradient(values):
    """用最近点权重和包络导数核对正距离、非退化三角形。"""
    p,a,b,c=[tuple(Fraction(float(x)) for x in row) for row in values]
    def sub(x,y): return tuple(u-v for u,v in zip(x,y))
    def dot(x,y): return sum(u*v for u,v in zip(x,y))
    def cross(x,y): return (x[1]*y[2]-x[2]*y[1],x[2]*y[0]-x[0]*y[2],x[0]*y[1]-x[1]*y[0])
    normal=cross(sub(b,a),sub(c,a))
    area=dot(normal,normal)
    kind,distance=point_triangle_reference(values)
    if not area or distance==0:
        raise ValueError("退化或零距离不按光滑三角面梯度解释")
    vertices=[a,b,c]
    weights=[Fraction(0)]*3
    if kind==0:
        height=dot(sub(p,a),normal)/area
        closest=tuple(x-height*n for x,n in zip(p,normal))
        weights=[dot(cross(sub(b,closest),sub(c,closest)),normal)/area,
            dot(cross(sub(c,closest),sub(a,closest)),normal)/area,
            dot(cross(sub(a,closest),sub(b,closest)),normal)/area]
    elif kind in [1,2,4]:
        index={1:0,2:1,4:2}[kind]
        weights[index]=Fraction(1)
        closest=vertices[index]
    else:
        first,last={3:(0,1),6:(1,2),5:(2,0)}[kind]
        direction=sub(vertices[last],vertices[first])
        parameter=dot(sub(p,vertices[first]),direction)/dot(direction,direction)
        weights[first]=1-parameter
        weights[last]=parameter
        closest=tuple(x+parameter*d for x,d in zip(vertices[first],direction))
    gradient=np.array([float(x) for x in sub(p,closest)])/distance
    return np.vstack([gradient,*[-float(weight)*gradient for weight in weights]])
