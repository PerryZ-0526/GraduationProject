"""在原生成/简化阶段做轴向尺度均衡，原第三阶段仍在物理坐标求解。"""
from pathlib import Path
from datetime import datetime,timezone,timedelta
import json
import numpy as np,torch,pamo,pamo_safe_project,locality_gpu

def metric_factors(vertices):
    extent=np.ptp(np.asarray(vertices,dtype=np.float64),axis=0)
    if not np.isfinite(extent).all() or np.any(extent<=0):raise ValueError('尺度均衡要求三维正有限包围盒')
    return np.exp2(np.floor(np.log2(extent.max()/extent)))

def install_balanced_metric(origin,mode,output):
    if mode not in ('stage2_only','stage12'):raise ValueError('仅允许先冻结的两个度量对照')
    origin=np.asarray(origin,dtype=np.float64);output=Path(output);output.mkdir(exist_ok=False)
    record={'生成时间':datetime.now(timezone(timedelta(hours=8))).isoformat(),'修改时间及修改内容':'首次生成，轴向二次幂度量对照','文档概述':'生成/简化轨迹改变，第三阶段还原物理单位；不称欧氏数值等价或全局优势','索引目录':['metric','projection'],'mode':mode,'physical_projection_calls':0}
    def save(): (output/'01-实际生成简化度量与物理投影绑定.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),'utf8')
    original_projection=pamo_safe_project.process
    if mode=='stage2_only':
        original_init=pamo.PaMO.__init__
        def constructor(self,*args,**kwargs):
            original_init(self,*args,**kwargs);factors=metric_factors(self.gt_mesh.vertices);record['factors']=factors.tolist();save();original_apply=self.func.apply;metric_scale=None
            def apply(vertices,faces,undo,n_undo,scale,threshold,is_stuck,init):
                nonlocal metric_scale
                # 只有首次初始化进入度量坐标，随后原CUDA内部状态和各轮输出都保持同一度量。
                if init:
                    weights=torch.tensor(factors,dtype=vertices.dtype,device=vertices.device);vertices=vertices*weights;metric_scale=(vertices.max(dim=0).values-vertices.min(dim=0).values).max();record['stage2_scale']=float(metric_scale.item());record['threshold_unchanged']=float(threshold);save()
                return original_apply(vertices,faces,undo,n_undo,metric_scale,threshold,is_stuck,init)
            self.func.apply=staticmethod(apply)
        pamo.PaMO.__init__=constructor
        def projection(gt_v,gt_f,v,f,*args,**kwargs):
            factors=np.asarray(record['factors']);record['physical_projection_calls']+=1;record['physical_GT_unchanged']=True;save();return original_projection(gt_v,gt_f,np.asarray(v)/factors,f,*args,**kwargs)
    else:
        original_full=locality_gpu.run_full
        def run_full(mesh,*args,**kwargs):
            factors=metric_factors(mesh.vertices);record['factors']=factors.tolist();save();transformed=mesh.copy();transformed.vertices=(mesh.vertices-origin)*factors+origin;result,details=original_full(transformed,*args,**kwargs)
            encoded=np.asarray((mesh.vertices-origin)*factors,dtype=np.float32);physical_error=np.linalg.norm(encoded.astype(np.float64)/factors+origin-mesh.vertices,axis=1);details['initial_metric_encoding_max_error']=details.pop('initial_encoding_max_error_mm');details.update(initial_encoding_max_error_mm=float(physical_error.max()),stage12_metric_factors=factors.tolist(),coordinate_encoding='balanced_stage12_metric_then_physical_stage3_and_world_origin');return result,details
        locality_gpu.run_full=run_full
        def projection(gt_v,gt_f,v,f,*args,**kwargs):
            factors=np.asarray(record['factors']);record['physical_projection_calls']+=1;record['physical_GT_inverse_restored']=True;save();return original_projection(np.asarray(gt_v)/factors,gt_f,np.asarray(v)/factors,f,*args,**kwargs)
    pamo_safe_project.process=projection
    save()
