"""恢复旧计划的参数与裁剪语义，不把旧示例称为真实术中记录。"""
from pathlib import Path
import sys
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'真实骨模型演示'))
import real_bone_demo as R


def original_plan():
    radii={'面粗':R.R_PLATE,'面精':R.R_PLATE,'台粗':R.R_BOSS,'台精':R.R_BOSS,'柱钻':R.R_POST}
    return [dict(step=i,phase=phase,radius=float(radius),start=list(a),end=list(b),clip_radius=radii[phase])
            for i,(phase,radius,a,b) in enumerate(R.trajectory(),1)]


def classify(item,candidate,chart):
    """对全部段独立做保守适用性诊断，不把这些段拼成成功序列。"""
    a,b=np.array(item['start']),np.array(item['end'])
    radius=item['radius']
    reasons=[]
    if a[2]!=b[2]:
        reasons.append('nonhorizontal')
    if max(np.linalg.norm(a[:2]),np.linalg.norm(b[:2]))+radius>item['clip_radius']:
        reasons.append('requires_plan_clipping')
    # 包围盒仅能证明不相交；可能碰到未重建原面时保守拒绝，不冒充精确碰撞。
    low,high=np.minimum(a,b)-radius,np.maximum(a,b)+radius
    triangles=chart.surface.mesh.triangles[candidate['keep']]
    outside=np.all(triangles.max(axis=1)>=low,axis=1)&np.all(triangles.min(axis=1)<=high,axis=1)
    if np.any(outside):
        reasons.append('outside_patch_possible')
    return reasons


def variant_trajectories():
    from real_patch import local_trajectory, Sweep
    base=local_trajectory(1.8)
    cases={'control':base}
    for name,offset,angle,z in [('shift_x_1',(1,0),0,1.8),('rotate_45',(0,0),np.pi/4,1.8),
                               ('deep_1p5',(0,0),0,1.5),('boundary_x4',(4,0),0,1.8)]:
        rotation=np.array([[np.cos(angle),-np.sin(angle)],[np.sin(angle),np.cos(angle)]])
        cases[name]=[Sweep(tuple(rotation@t.start+offset),tuple(rotation@t.end+offset),t.radius,z) for t in base]
    cases['fine_32']=[s for t in base for s in (Sweep(t.start,tuple((np.array(t.start)+t.end)/2),t.radius,t.z),
                  Sweep(tuple((np.array(t.start)+t.end)/2),t.end,t.radius,t.z))]
    cases['coarse_8']=[Sweep(base[i].start,base[i+1].end,base[i].radius,base[i].z) for i in range(0,16,2)]
    return cases
