"""保留上一冻结批次的完整角度NaN检查，用作范围安全分支的同次对照。"""
import numpy as np


def check_and_boxes(vertices,faces):
    points=vertices[faces]
    edges=np.roll(points,-1,axis=1)-points
    lengths=np.linalg.norm(edges,axis=-1)
    area=np.linalg.norm(np.cross(edges[:,0],-edges[:,2]),axis=-1)/2
    valid=np.isfinite(area)&(area>1e-12)
    for k in range(3):
        previous=(k+2)%3
        denominator=lengths[:,k]*lengths[:,previous]
        numerator=-(edges[:,k]*edges[:,previous]).sum(-1)
        # 保留旧版除法与NaN判据，极端输入和正常输入均执行全部角度中间量。
        cosine=np.divide(numerator,denominator,out=np.ones_like(denominator),where=denominator>0)
        valid&=~np.isnan(cosine)
    a,b,c=points[:,0],points[:,1],points[:,2]
    return int((~valid).sum()),np.minimum(np.minimum(a,b),c),np.maximum(np.maximum(a,b),c)
