"""同一进程内的Geogram数组差集；调用方仍负责输入闭合嵌入和输出核查。"""
import ctypes as C
import os
import sys
from pathlib import Path
from time import perf_counter
import numpy as np


class GeogramMemory:
    def __init__(self):
        workspace=Path(__file__).resolve().parents[2]
        # Linux库由同冻结Geogram源码编译并绑定私有RPATH，避免加载共享旧版本。
        if sys.platform=='win32':
            self.dll_directory=os.add_dll_directory(str(workspace/'tmp/实时预算Geogram本机编译/bin/Release'))
            path=workspace/'tmp/实时预算内存布尔编译/Release/geogram_memory.dll'
        # Linux库加lib前缀，避免与当前Python包装器发生扩展模块导入冲突。
        else:path=Path(__file__).with_name('libgeogram_memory.so')
        self.lib=C.CDLL(str(path))
        ptr=C.c_void_p; count=C.c_uint64
        self.lib.difference_arrays.argtypes=[ptr,count,ptr,count,ptr,count,ptr,count,ptr,ptr,ptr,count,C.c_int]
        self.lib.difference_arrays.restype=ptr
        self.lib.copy_result.argtypes=[ptr,ptr,ptr,ptr]
        self.lib.release_result.argtypes=[ptr]
        self.lib.copy_result.restype=None; self.lib.release_result.restype=None

    def difference(self, av, af, bv, bf,no_simplify=False):
        start=perf_counter()
        av=np.ascontiguousarray(av,dtype=np.float64); bv=np.ascontiguousarray(bv,dtype=np.float64)
        af=np.ascontiguousarray(af,dtype=np.int64); bf=np.ascontiguousarray(bf,dtype=np.int64)
        for v,f in ((av,af),(bv,bf)):
            if v.ndim!=2 or v.shape[1]!=3 or f.ndim!=2 or f.shape[1]!=3:
                raise ValueError('内存布尔输入必须是三维顶点和三角面数组')
        counts=np.zeros(2,dtype=np.uint64); times=np.zeros(3,dtype=np.float64)
        error=C.create_string_buffer(1024)
        handle=self.lib.difference_arrays(av.ctypes.data,len(av),af.ctypes.data,len(af),
            bv.ctypes.data,len(bv),bf.ctypes.data,len(bf),counts.ctypes.data,times.ctypes.data,error,1024,int(no_simplify))
        if not handle: raise RuntimeError(error.value.decode('utf-8',errors='replace'))
        copy_start=perf_counter()
        try:
            v=np.empty((int(counts[0]),3),dtype=np.float64)
            f=np.empty((int(counts[1]),3),dtype=np.int64)
            bits=np.empty(int(counts[1]),dtype=np.int64)
            self.lib.copy_result(handle,v.ctypes.data,f.ctypes.data,bits.ctypes.data)
        finally:
            self.lib.release_result(handle)
        # 总时间包括数组适配、作者初始化、输入构建、差集、输出复制和释放。
        timing={'initialization_ms':float(times[0]),'input_copy_ms':float(times[1]),
                'boolean_ms':float(times[2]),'output_copy_release_ms':(perf_counter()-copy_start)*1000,
                'total_ms':(perf_counter()-start)*1000,'no_simplify':bool(no_simplify)}
        return v,f,bits,timing
