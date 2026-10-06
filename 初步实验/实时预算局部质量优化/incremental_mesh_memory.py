"""原生不可伪造父证书与变化面精确核查；证书只在调用方接受结果后替换。"""
import ctypes as C
import sys
from pathlib import Path
from time import perf_counter
import numpy as np


class VerifiedMesh:
    def __init__(self):
        # 相同原生证书在Linux实例从工作器旁加载，Windows仍使用原编译目录。
        path=(Path(__file__).resolve().parents[2]/'tmp/实时预算内存布尔编译/Release/incremental_mesh_memory.dll'
              if sys.platform=='win32' else Path(__file__).with_name('libincremental_mesh_memory.so'))
        self.lib=C.CDLL(str(path))
        p=C.c_void_p;n=C.c_uint64
        self.lib.create_verified_state.argtypes=[p,n,p,n,p,p];self.lib.create_verified_state.restype=p
        self.lib.audit_transition.argtypes=[p,p,n,p,n,p,p,p];self.lib.audit_transition.restype=C.c_int
        self.lib.release_verified_state.argtypes=[p];self.lib.release_verified_state.restype=None
        self.lib.audit_fixed_flips.argtypes=[p,p,n,p,n,p,n,p,p];self.lib.audit_fixed_flips.restype=C.c_int
        self.handle=None

    def close(self):
        if self.handle:self.lib.release_verified_state(self.handle);self.handle=None

    def check(self,vertices,faces,advance=False):
        start=perf_counter();v=np.ascontiguousarray(vertices,dtype=np.float64);f=np.ascontiguousarray(faces,dtype=np.int64)
        if v.ndim!=2 or v.shape[1]!=3 or f.ndim!=2 or f.shape[1]!=3:raise ValueError('精确证书数组形状错误')
        result=np.zeros(12,dtype=np.int64);timings=np.zeros(4);next_handle=C.c_void_p()
        root=self.handle is None
        if root:
            next_handle.value=self.lib.create_verified_state(v.ctypes.data,len(v),f.ctypes.data,len(f),result.ctypes.data,timings.ctypes.data)
        else:
            code=self.lib.audit_transition(self.handle,v.ctypes.data,len(v),f.ctypes.data,len(f),result.ctypes.data,timings.ctypes.data,C.byref(next_handle))
            if code:raise RuntimeError(f'变化面精确核查失败，返回码{code}')
        accepted=bool(result[6]) and bool(next_handle.value)
        if advance and accepted:
            self.close();self.handle=next_handle.value
        elif next_handle.value:self.lib.release_verified_state(next_handle)
        report=dict(root_full_audit=root,topology_valid=bool(result[1]),closed=bool(result[4]),embedded_closed=accepted,
            self_intersection_pairs=int(result[5]),exact_degenerate_faces=int(result[7]),inherited_faces=int(result[8]),
            exact_pairs_checked=int(result[9]),unchanged_pairs_inherited=int(result[10]),unchanged_pairs_not_enumerated=not root,advanced=bool(advance and accepted),
            native_ms=timings.tolist())
        # 建立下一证书、释放未采用证书及Python结果组织均计入总时间。
        report['total_elapsed_ms']=(perf_counter()-start)*1000
        return report

    def check_flips(self,vertices,faces,operations):
        """原生重新核查完整操作记录和实际数组；成功才在原证书中提交固定顶点翻边。"""
        start=perf_counter()
        if self.handle is None:raise ValueError('翻边必须绑定实际精确父证书')
        v=np.ascontiguousarray(vertices,dtype=np.float64);f=np.ascontiguousarray(faces,dtype=np.int64)
        if v.ndim!=2 or v.shape[1]!=3 or f.ndim!=2 or f.shape[1]!=3:raise ValueError('精确翻边数组形状错误')
        if len(operations)>16:raise ValueError('一次精确翻边提交最多16项')
        rows=[]
        for op in operations:
            owners=np.asarray(op['faces'],dtype=np.int64);before=np.asarray(op['before'],dtype=np.int64);after=np.asarray(op['after'],dtype=np.int64)
            if owners.shape!=(2,) or before.shape!=(2,3) or after.shape!=(2,3):raise ValueError('精确翻边操作记录形状错误')
            rows.append(np.concatenate((owners,before.ravel(),after.ravel())))
        ops=np.ascontiguousarray(rows,dtype=np.int64).reshape(-1,14)
        result=np.zeros(12,dtype=np.int64);timings=np.zeros(4)
        code=self.lib.audit_fixed_flips(self.handle,v.ctypes.data,len(v),f.ctypes.data,len(f),ops.ctypes.data,len(ops),result.ctypes.data,timings.ctypes.data)
        if code:raise RuntimeError(f'固定翻边精确核查失败，返回码{code}')
        accepted=bool(result[6])
        report=dict(root_full_audit=False,topology_valid=bool(result[1]),closed=bool(result[4]),embedded_closed=accepted,
            advanced=accepted,fixed_vertex_operation_certificate=True,verified_operations=int(result[8]),exact_pairs_checked=int(result[9]),
            unchanged_pairs_not_enumerated=True,native_ms=timings.tolist(),rejection_code=int(result[11]),
            collision_faces=[int(result[2]),int(result[3])] if result[11]==10 else None)
        # 输入适配、记录组织、原生拓扑事务及结果组织全部计入预算。
        report['total_elapsed_ms']=(perf_counter()-start)*1000
        return report
