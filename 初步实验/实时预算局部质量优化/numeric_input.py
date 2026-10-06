"""只做维护必需的数值有效性检查与包围盒，不计算全网格角度分布。"""
import numpy as np


def check_and_boxes(vertices,faces,minimum_area_mm2=1e-12):
    a,b,c=(vertices[faces[:,k]] for k in range(3))
    area=np.linalg.norm(np.cross(b-a,c-a),axis=-1)/2
    # 历史默认判据保持；自身固定顶点算法可明确选择正面积输入，嵌入仍由调用方核查。
    valid=np.isfinite(area)&(area>minimum_area_mm2)
    # 坐标绝对值不超过sqrt(MAX)/16时，边分量不超过sqrt(MAX)/8。
    # 三项点积、范数平方及范数乘积均有足够余量保持有限；非零除数不会产生NaN。
    # 除法溢出产生的无穷在原夹取后仍是有限角度，因此只需保留相同面积判据。
    # 这是浮点中间量的安全范围证明，不是新的几何容差或退化面放宽规则。
    # 使用输入自身精度的范围；整数输入不采用这条浮点安全分支。
    safe_limit=np.sqrt(np.finfo(vertices.dtype).max)/16 if vertices.dtype.kind=='f' else None
    if safe_limit is not None and np.max(np.abs(vertices),initial=0)<=safe_limit:
        return int((~valid).sum()),np.minimum(np.minimum(a,b),c),np.maximum(np.maximum(a,b),c)
    # 极端坐标仍按原三个角的NaN分支检查，不将安全范围证明外推到这些输入。
    points=vertices[faces]
    edges=np.roll(points,-1,axis=1)-points
    lengths=np.linalg.norm(edges,axis=-1)
    for k in range(3):
        previous=(k+2)%3
        denominator=lengths[:,k]*lengths[:,previous]
        numerator=-(edges[:,k]*edges[:,previous]).sum(-1)
        # 与原角度计算的除法分支相同；夹到[-1,1]后只有NaN会产生非有限角度。
        cosine=np.divide(numerator,denominator,out=np.ones_like(denominator),where=denominator>0)
        valid&=~np.isnan(cosine)
    return int((~valid).sum()),np.minimum(np.minimum(a,b),c),np.maximum(np.maximum(a,b),c)
