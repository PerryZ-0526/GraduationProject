"""明确加载同目录精确整数守卫；不支持或加载失败时不悄悄换成近似判定。"""
import ctypes
import sys
from pathlib import Path
from time import perf_counter
import numpy as np
from local_guard import LocalGuard

_library=None


def load_library():
    global _library
    if _library is None:
        # Windows运行本机明确编译的动态库；Linux继续加载冻结工作器相邻的原生库。
        path=(Path(__file__).resolve().parents[2]/'tmp/实时预算内存布尔编译/Release/local_separation.dll'
              if sys.platform=='win32' else Path(__file__).with_name('local_separation.so'))
        library=ctypes.CDLL(str(path))
        pointer=ctypes.c_void_p
        library.separate_triangles.argtypes=[pointer,pointer,ctypes.c_double]
        library.separate_triangles.restype=ctypes.c_int
        library.separation_clock.argtypes=[];library.separation_clock.restype=ctypes.c_double
        # 只有本机精确调用时钟与Python截止时钟共享原点时，才能使用轴内超时检查。
        before=perf_counter();now=library.separation_clock();after=perf_counter()
        if not before<=now<=after:raise RuntimeError('原生守卫与Python截止时钟不一致')
        _library=library
    return _library


def separated_native(vertices,first,second,deadline):
    ids=np.ascontiguousarray(tuple(first)+tuple(second),dtype=np.int64)
    points=np.ascontiguousarray(vertices[ids],dtype=np.float64)
    result=load_library().separate_triangles(points.ctypes.data,ids.ctypes.data,deadline)
    if result==-2:raise ValueError('原生守卫输入坐标非有限')
    return result==1


class NativeLocalGuard(LocalGuard):
    separation_check=staticmethod(separated_native)
