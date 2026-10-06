"""原生全域扫描只缩小候选列表，保留原范数阈值和候选次序。"""
import ctypes
from pathlib import Path
import numpy as np

_library=None


def prepare_short_edges(vertices,faces,tolerance):
    global _library
    # 当前物理毫米容差为1e-10；限制正常数范围，避免宽筛的平方下溢或上溢。
    if not 1e-150<=tolerance<=1e150:raise ValueError('原生宽筛仅支持正常物理容差')
    if _library is None:
        _library=ctypes.CDLL(str(Path(__file__).with_name('libshort_edge_scan.so')))
        _library.scan_short_edges.argtypes=[ctypes.c_void_p,ctypes.c_int64,ctypes.c_void_p,ctypes.c_int64,
            ctypes.c_double,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p]
        _library.scan_short_edges.restype=ctypes.c_int64
    v=np.ascontiguousarray(vertices,dtype=np.float64);f=np.ascontiguousarray(faces,dtype=np.int64)
    if v.ndim!=2 or v.shape[1]!=3 or f.ndim!=2 or f.shape[1]!=3:raise ValueError('顶点或三角面维数不合法')
    low=np.empty((len(f),3));high=np.empty_like(low);edges=np.empty((3*len(f),2),dtype=np.int64)
    count=_library.scan_short_edges(v.ctypes.data,len(v),f.ctypes.data,len(f),tolerance,
        low.ctypes.data,high.ctypes.data,edges.ctypes.data)
    if count<0:raise ValueError('原生宽筛遇到非法容差、索引或非有限坐标')
    edges=edges[:count]
    # 仍使用原实现的归一化前FP64范数，边界、去重与字典序均不改变。
    distance=np.linalg.norm(v[edges[:,0]]-v[edges[:,1]],axis=1)
    candidates=np.unique(edges[distance<=tolerance],axis=0)
    return low,high,candidates
