"""本机完整核查保存binary64几何，使用无外部GMP依赖的EPECK准确后端。"""
import ctypes as C
import sys
from pathlib import Path
from time import perf_counter
import numpy as np


class ExactMeshMemory:
    def __init__(self):
        # Linux加载实际冻结工作器旁的库；Windows保留已有明确编译位置。
        path=(Path(__file__).resolve().parents[2]/'tmp/实时预算内存布尔编译/Release/exact_mesh_memory.dll'
              if sys.platform=='win32' else Path(__file__).with_name('libexact_mesh_memory.so'))
        self.lib=C.CDLL(str(path))
        self.lib.audit_arrays.argtypes=[C.c_void_p,C.c_uint64,C.c_void_p,C.c_uint64,C.c_void_p,C.c_void_p]
        self.lib.audit_arrays.restype=C.c_int

    def audit(self,vertices,faces):
        start=perf_counter();v=np.ascontiguousarray(vertices,dtype=np.float64);f=np.ascontiguousarray(faces,dtype=np.int64)
        if v.ndim!=2 or v.shape[1]!=3 or f.ndim!=2 or f.shape[1]!=3:raise ValueError('嵌入核查数组形状非法')
        result=np.zeros(8,dtype=np.int64);timings=np.zeros(3,dtype=np.float64)
        code=self.lib.audit_arrays(v.ctypes.data,len(v),f.ctypes.data,len(f),result.ctypes.data,timings.ctypes.data)
        if code:raise RuntimeError(f'完整精确内存核查失败，返回码{code}')
        report=dict(parsed=bool(result[0]),topology_valid=bool(result[1]),vertices=int(result[2]),faces=int(result[3]),
            closed=bool(result[4]),self_intersection_pairs=int(result[5]),embedded_closed=bool(result[6]),
            exact_degenerate_faces=int(result[7]),kernel='EPECK_without_GMP_Quotient_MP_Float',
            native_build_ms=float(timings[0]),native_degenerate_check_ms=float(timings[1]),native_intersection_ms=float(timings[2]))
        # Python数组适配、结果组织及原生对象释放全部计入返回总时间。
        report['total_elapsed_ms']=(perf_counter()-start)*1000
        return report
