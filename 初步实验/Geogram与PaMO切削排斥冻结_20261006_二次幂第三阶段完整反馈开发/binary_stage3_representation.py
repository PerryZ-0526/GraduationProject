"""保留工具原点的二次幂第三阶段表示，物理长度与能量量纲同步换算。"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import hashlib, inspect, json, subprocess
import numpy as np
import trimesh
import warp as wp

def install_binary_stage3_representation(output):
 import pamo_safe_project as package
 from pamo_safe_project import processing
 from pamo_safe_project.system import Stage3System
 from pamo_safe_project.config import Stage3Config
 output=Path(output);output.mkdir(exist_ok=False)
 checker=Path('/root/autodl-tmp/graduation_project/exact_mesh_audit_20261004_0646')
 assert hashlib.sha256(checker.read_bytes()).hexdigest()=='0af22fcb7cad4de31524cd09d5b143a3716f53c81d5c271a218307da05adcdd3'
 for item,digest in [(processing,'a4197a135323d955c8c6b4c55dc4a63701447713020b82206d3d14a39554a4c8'),(Stage3System,'bb6c38d3e644fad99bd4bdbf3e3402fae2afa161a46bd5dcdc38b7f1c6183474'),(Stage3Config,'df1eb24db57394c32e31f6d67a58cd7ef6c25febc11aff39c5e9503ee82d6390')]:
  assert hashlib.sha256(Path(inspect.getfile(item)).read_bytes()).hexdigest()==digest
 original_process=processing.process; original_transform=processing.get_normalization_transform
 def process(gt_V,gt_F,stage2_V,stage2_F,n_iters,system=None,config=None,eval=False,return_curve=False):
  if system is None: raise ValueError('本隔离入口只适配已构造的完整PaMO第三阶段系统')
  c=system.config
  assert config is None or config is c
  assert c.system_scale==1.0
  author_scale,t=original_transform(gt_V);scale=float(2.**np.floor(np.log2(author_scale)));alpha=scale/author_scale
  rec={'生成时间':datetime.now(timezone(timedelta(hours=8))).isoformat(),'修改时间及修改内容':'首次生成，本刀实际第三阶段表示与完整求解','文档概述':'保留完整碰撞和CCD，物理长度不变；量纲换算不声称有限精度数值等价','索引目录':['parameters','gates','solver'],'scale':scale,'author_scale':float(author_scale),'author_translation':t.tolist(),'alpha':float(alpha),'gates':[],'diff_calls':0,'ccd_calls':0,'status':'checking'}
  def save(): (output/'01-第三阶段实际表示与求解记录.json').write_text(json.dumps(rec,ensure_ascii=False,indent=2),'utf8')
  # 不改变弹性与碰撞权重，距离除以alpha平方、铰链乘alpha，使各项共享alpha平方能量因子。
  fields=['d_hat','contact_detection_radius','ccd_thickness','mesh2gt_dist_stiffness','gt2mesh_dist_stiffness','hinge_stiffness']
  saved={k:getattr(c,k) for k in fields}
  for k in fields[:3]:setattr(c,k,saved[k]*alpha)
  for k in fields[3:5]:setattr(c,k,saved[k]/alpha**2)
  c.hinge_stiffness=saved['hinge_stiffness']*alpha
  rec['parameters']={k:v for k,v in vars(c).items() if k!='energy_calcs'}
  rec['energy_calcs']=[x.__name__ for x in c.energy_calcs];save()
  old_register,old_diff,old_ccd=system.register_mesh,system._compute_diff,system._ccd
  def register(V_gt,F_gt,V,F):
   arrays=[]
   for name,xyz,faces in [('候选',V,F),('源',V_gt,F_gt)]:
    # 读取真实Warp FP32数组，再用原生精确检查；未通过时不得进入能量预处理。
    encoded=wp.array(xyz,dtype=wp.vec3,device=system.device).numpy();arrays.append(encoded)
    p=output/(name+'实际Warp编码.obj')
    with p.open('w',encoding='utf8') as stream:
     for point in encoded:stream.write('v '+' '.join(format(float(x),'.17g') for x in point)+'\n')
     for ids in faces:stream.write('f '+' '.join(str(int(x)+1) for x in ids)+'\n')
    run=subprocess.run([str(checker),str(p)],capture_output=True,text=True,check=True);embedding=json.loads(run.stdout)
    mesh=trimesh.Trimesh(encoded.astype(np.float64)/scale,faces,process=False)
    row={'role':name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'embedding':embedding,'finite':bool(np.isfinite(encoded).all()),'zero_area_faces':int((mesh.area_faces==0).sum()),'small_faces_mm2':int((mesh.area_faces<=1e-12).sum())}
    rec['gates'].append(row);save()
    if not row['finite'] or not embedding['embedded_closed'] or row['zero_area_faces'] or (name=='候选' and row['small_faces_mm2']):raise RuntimeError('实际第三阶段表示拒绝:'+name)
   old_register(V_gt,F_gt,V,F)
   assert np.array_equal(system.q.numpy()[:system.n_particles],arrays[0]) and np.array_equal(system.gt_vertices.numpy()[:system.n_gt_particles],arrays[1])
   rec['author_do_nothing']=bool(system.do_nothing);save()
  def diff():
   old_diff();rec['diff_calls']+=1
   for name in ['energy','grad','hess_diag']:
    value=getattr(system,name).numpy();value=value[:system.n_particles] if name!='energy' else value
    if not np.isfinite(value).all():raise RuntimeError('原第三阶段求导非有限:'+name)
  def ccd():
   if not np.isfinite(system.p.numpy()[:system.n_particles]).all():raise RuntimeError('原CG方向非有限')
   old_ccd();rec['ccd_calls']+=1
   if not np.isfinite(system.ccd_step.numpy()).all():raise RuntimeError('原CCD非有限')
  system.register_mesh,system._compute_diff,system._ccd=register,diff,ccd
  processing.get_normalization_transform=lambda V:(scale,np.zeros(3))
  try:
   result=original_process(gt_V,gt_F,stage2_V,stage2_F,n_iters,system,c,eval,return_curve)
   rec['status']='completed_original_solver';return result
  except Exception as error:
   rec['status']='rejected_with_recorded_evidence';rec['error']=repr(error);raise
  finally:
   processing.get_normalization_transform=original_transform
   system.register_mesh,system._compute_diff,system._ccd=old_register,old_diff,old_ccd
   for k,v in saved.items():setattr(c,k,v)
   rec['finished_beijing']=datetime.now(timezone(timedelta(hours=8))).isoformat();save()
 package.process=process
 processing.process=process
