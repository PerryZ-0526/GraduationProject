"""固定浮点坐标的有理数最近点分类与平方距离，仅供小规模独立对拍。"""
from fractions import Fraction
import math


def point_triangle_reference(values):
    """先以精确三边测试判定投影内外，外部比较三个闭线段的最近点。"""
    p,a,b,c=[tuple(Fraction(float(x)) for x in row) for row in values]
    def sub(x,y): return tuple(u-v for u,v in zip(x,y))
    def dot(x,y): return sum(u*v for u,v in zip(x,y))
    def cross(x,y): return (x[1]*y[2]-x[2]*y[1],x[2]*y[0]-x[0]*y[2],x[0]*y[1]-x[1]*y[0])
    normal=cross(sub(b,a),sub(c,a))
    area=dot(normal,normal)
    if area and all(dot(cross(sub(end,start),sub(p,start)),normal)>=0 for start,end in [(a,b),(b,c),(c,a)]):
        numerator=dot(sub(p,a),normal)
        return 0,math.sqrt(float(numerator*numerator/area))
    candidates=[]
    for start,end,edge,first,last in [(a,b,3,1,2),(b,c,6,2,4),(c,a,5,4,1)]:
        direction=sub(end,start)
        denominator=dot(direction,direction)
        t=min(Fraction(1),max(Fraction(0),dot(sub(p,start),direction)/denominator)) if denominator else Fraction(0)
        closest=tuple(v+t*d for v,d in zip(start,direction))
        delta=sub(p,closest)
        candidates.append((dot(delta,delta),first if t==0 else last if t==1 else edge))
    best=min(enumerate(candidates),key=lambda item:(item[1][0],item[0]))[1]
    return best[1],math.sqrt(float(best[0]))
