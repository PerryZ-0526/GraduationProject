"""完整扫掠工具批量切削，合法源认证后接原轻量CUDA质量处理。"""
from time import perf_counter
import numpy as np
from resident_batch_boolean_service import BatchBooleanService,BatchBooleanFailure
from incremental_mesh_memory import VerifiedMesh
from numeric_input import check_and_boxes
from covered_zero_cleanup import clean_arrays
from short_edge_repair import repair_short_edges
from native_guard import NativeLocalGuard,separated_native
from maintain_input import maintain_input
from resident_source_cleanup import cancel_opposed_index_faces,repair_short_edge_clusters


class ResidentBatchEngine:
    def __init__(self,vertices,faces,quality_enabled=True):
        self.vertices=np.ascontiguousarray(vertices,dtype=np.float64).copy()
        self.faces=np.ascontiguousarray(faces,dtype=np.int64).copy()
        self.bits=np.ones(len(faces),dtype=np.int64)
        self.certificate=VerifiedMesh()
        self.root_check=self.certificate.check(self.vertices,self.faces,advance=True)
        if not self.root_check['embedded_closed']:raise ValueError('批量链初态未通过完整精确认证')
        # 原生计算隔离到常驻进程；根认证成功后才启动，启动时间单列于在线服务之外。
        self.api=BatchBooleanService()
        self.quality_enabled=quality_enabled

    def close(self):self.certificate.close();self.api.close()

    def step(self,tools):
        started=perf_counter();parent=self.vertices
        try:rv,rf,rb,boolean=self.api.difference_batch(self.vertices,self.faces,tools,certified_operands=True)
        except BatchBooleanFailure as error:
            # 计算器失败没有可认证的新源；保留原合法父网格并明确区分执行失败与非法源。
            return dict(published=False,failed_stage='boolean',error=repr(error),
                service_ms=(perf_counter()-started)*1000),dict(parent=(self.vertices,self.faces,self.bits))
        v,f,bits=rv,rf,rb.copy();maintenance_start=perf_counter()
        # 来源位保持每件工具身份，并限定于本次真实操作数域。
        if np.any(bits<=0) or np.any(bits>((1<<(len(tools)+1))-1)):
            raise ValueError('批量输出来源位超出真实操作数域')
        invalid,_,_=check_and_boxes(v,f,0);cleanup=None;cluster=None
        if invalid:v,f,bits,cleanup=clean_arrays(v,f,bits)
        remaining=200-(perf_counter()-maintenance_start)*1000
        # 沿用同父组件对照的必要修复预算、自然收缩上限和全部守卫。
        v,f,bits,repair=repair_short_edges(v,f,bits,parent,max(0,remaining-50),
            max_collapses=len(f)//2,separation_check=separated_native)
        v,f,bits,opposed=cancel_opposed_index_faces(v,f,bits)
        invalid,_,_=check_and_boxes(v,f,0)
        if invalid and not np.isfinite(v).all():raise ValueError('批量修复后坐标仍非有限')
        check=(dict(embedded_closed=False,advanced=False,numeric_invalid_source=True)
            if invalid else self.certificate.check(v,f,advance=True))
        if not check['embedded_closed']:
            nv,nf,nb,cluster=repair_short_edge_clusters(v,f,bits,parent,tolerance_mm=5e-9)
            cluster['original_failed_check']=check
            if cluster['candidate']:
                candidate_check=self.certificate.check(nv,nf,advance=True)
                cluster['candidate_check']=candidate_check
                if candidate_check['embedded_closed']:v,f,bits,check=nv,nf,nb,candidate_check
        source=(v.copy(),f.copy(),bits.copy())
        preparation=dict(accepted=check['embedded_closed'],check=check,cleanup=cleanup,
            repair=repair,opposed=opposed,cluster=cluster)
        maintenance=None;final_check=None
        if check['embedded_closed']:
            remaining=200-(perf_counter()-maintenance_start)*1000
            if self.quality_enabled and remaining>45:
                # 活动邻域覆盖本批全部工具；不把来源位合并，也不只使用最后一个工具范围。
                low=np.minimum.reduce([tv.min(axis=0) for tv,tf in tools])
                high=np.maximum.reduce([tv.max(axis=0) for tv,tf in tools])
                state,maintenance=maintain_input(v,f,bits,low,high,min(30,remaining-15),
                    guard_class=NativeLocalGuard,minimum_input_area_mm2=0,max_flips=4,edge_backend='cuda')
                if maintenance['accepted']:
                    final_check=self.certificate.check_flips(state.vertices,state.faces,maintenance['operations'])
                    if final_check['embedded_closed']:v,f,bits=state.vertices,state.faces,state.bits
            # 复制实际发布数组计入服务时间，保存和离线复审由调用方另计。
            self.vertices,self.faces,self.bits=v.copy(),f.copy(),bits.copy()
            output=(self.vertices,self.faces,self.bits)
        else:output=None
        return dict(published=output is not None,boolean=boolean,preparation=preparation,
            maintenance=maintenance,final_check=final_check,
            maintenance_ms=(perf_counter()-maintenance_start)*1000,
            service_ms=(perf_counter()-started)*1000),dict(raw=(rv,rf,rb),source=source,output=output)
