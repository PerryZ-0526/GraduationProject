"""从常驻网格数组维护：输入有效性、活动域和共享包围盒都计入总预算。"""
from time import perf_counter
import numpy as np
from benchmark import quality
from local_guard import LocalGuard
from resumable_budget_flip import ResumableBudgetFlipState
from targeted_budget_flip import TargetedBudgetFlipState
from numeric_input import check_and_boxes


def maintain_input(vertices,faces,bits,tool_low,tool_high,budget_ms,backend='cpu',targeted=True,full_statistics=False,guard_class=LocalGuard,minimum_input_area_mm2=1e-12,max_flips=16,edge_backend='cpu'):
    """调用方提供已核查嵌入的源；此处数值核查不能替代任意新CSG输入的嵌入证明。"""
    start=perf_counter()
    # 全量角度分布仅作为对照，实时默认保留同口径的必需数值检查。
    before=quality(vertices,faces,minimum_input_area_mm2) if full_statistics else None
    if full_statistics:
        invalid=before['invalid'];a,b,c=(vertices[faces[:,k]] for k in range(3))
        low=np.minimum(np.minimum(a,b),c);high=np.maximum(np.maximum(a,b),c)
    else:
        # 历史默认仍调用原两参数接口，保留冻结消融对照的检查器替换约定。
        invalid,low,high=(check_and_boxes(vertices,faces) if minimum_input_area_mm2==1e-12
                         else check_and_boxes(vertices,faces,minimum_input_area_mm2))
    if invalid:raise ValueError('维护输入含无效三角形')
    active=np.all(high>=tool_low,axis=1)&np.all(low<=tool_high,axis=1)
    adapted=perf_counter()
    def factory(v,f):
        # 明确选择的守卫只替换实现；盒子来自同次计时原数组，提交后仍按两面更新。
        guard=object.__new__(guard_class)
        guard.vertices=v;guard.faces=f;guard.tolerance=1e-10
        guard.low=low;guard.high=high
        return guard
    method=TargetedBudgetFlipState if targeted else ResumableBudgetFlipState
    # CUDA准备只负责原有小角种子方法的稳定边排序，不改变CPU质量与几何提交条件。
    if edge_backend=='cuda':
        if not targeted:raise ValueError('CUDA边索引仅用于小角种子方法')
        from gpu_edge_index import CudaPreparedBudgetFlipState
        method=CudaPreparedBudgetFlipState
    elif edge_backend!='cpu':raise ValueError('边索引后端必须是cpu或cuda')
    state=method(vertices,faces,bits,active,backend,factory)
    remaining=max(0,budget_ms-(perf_counter()-start)*1000-4)
    # 在线快速策略可在少量质量操作完成后立即返回，默认继续保留历史16次对照。
    result=state.maintain(remaining,max_flips=max_flips)
    total=(perf_counter()-start)*1000
    result.update(total_budget_ms=budget_ms,total_elapsed_ms=total,total_budget_overrun=total>budget_ms,
        input_adapter_ms=(adapted-start)*1000,preparation_ms=state.preparation_ms,reserved_ms=4,
        active_faces=int(active.sum()),seed_bad_faces=getattr(state,'seed_bad_faces',None),active_edge_groups=len(state.edges),before=before,max_flips=max_flips,
        input_invalid_faces=invalid,minimum_input_area_mm2=minimum_input_area_mm2,full_before_statistics_included=full_statistics,edge_preparation_backend=edge_backend,
        input_embedding_is_caller_precondition=True,file_load_excluded=True,full_quality_after_excluded=True)
    # 返回统计的组织也计入总时间，最终两项时钟字段在返回前刷新。
    result['total_elapsed_ms']=(perf_counter()-start)*1000
    result['total_budget_overrun']=result['total_elapsed_ms']>budget_ms
    return state,result
