"""保留全部工具的多操作数差集；调用方须分别认证骨面和每件工具。"""
import ctypes as C
from time import perf_counter
import numpy as np
from geogram_memory import GeogramMemory


class GeogramBatchMemory(GeogramMemory):
    def __init__(self):
        super().__init__();pointer=C.c_void_p;count=C.c_uint64
        self.lib.batch_difference_arrays.argtypes=[pointer,count,pointer,count,pointer,pointer,
            pointer,pointer,count,pointer,pointer,pointer,count,C.c_int]
        self.lib.batch_difference_arrays.restype=pointer

    def difference_batch(self,vertices,faces,tools,no_simplify=True,certified_operands=False):
        start=perf_counter();v=np.ascontiguousarray(vertices,dtype=np.float64);f=np.ascontiguousarray(faces,dtype=np.int64)
        if not 1<=len(tools)<=31:raise ValueError('批次需要1至31件独立工具')
        inputs=[(v,f)]+[(np.ascontiguousarray(a,dtype=np.float64),np.ascontiguousarray(b,dtype=np.int64)) for a,b in tools]
        for a,b in inputs:
            if a.ndim!=2 or a.shape[1]!=3 or b.ndim!=2 or b.shape[1]!=3:raise ValueError('多工具布尔需要三维点和三角面')
        tool_v=np.ascontiguousarray(np.vstack([a for a,b in inputs[1:]]))
        tool_f=np.ascontiguousarray(np.vstack([b for a,b in inputs[1:]]))
        vertex_counts=np.array([len(a) for a,b in inputs[1:]],dtype=np.uint64)
        face_counts=np.array([len(b) for a,b in inputs[1:]],dtype=np.uint64)
        counts=np.zeros(2,dtype=np.uint64);times=np.zeros(3);error=C.create_string_buffer(1024)
        handle=self.lib.batch_difference_arrays(v.ctypes.data,len(v),f.ctypes.data,len(f),
            tool_v.ctypes.data,vertex_counts.ctypes.data,tool_f.ctypes.data,face_counts.ctypes.data,len(tools),
            counts.ctypes.data,times.ctypes.data,error,1024,int(no_simplify)|(2 if certified_operands else 0))
        if not handle:raise RuntimeError(error.value.decode('utf-8',errors='replace'))
        copy_start=perf_counter()
        try:
            result_v=np.empty((int(counts[0]),3));result_f=np.empty((int(counts[1]),3),dtype=np.int64)
            bits=np.empty(int(counts[1]),dtype=np.int64)
            self.lib.copy_result(handle,result_v.ctypes.data,result_f.ctypes.data,bits.ctypes.data)
        finally:self.lib.release_result(handle)
        # 拼接、作者计算、结果复制和释放均计入服务时间，未省去中间轨迹工具。
        return result_v,result_f,bits,dict(initialization_ms=float(times[0]),input_copy_ms=float(times[1]),
            boolean_ms=float(times[2]),output_copy_release_ms=(perf_counter()-copy_start)*1000,
            total_ms=(perf_counter()-start)*1000,tool_count=len(tools),expression='x0-('+'+'.join('x'+str(i+1) for i in range(len(tools)))+')',
            operand_bits_preserved=True,certified_operands=certified_operands,no_simplify=no_simplify)
