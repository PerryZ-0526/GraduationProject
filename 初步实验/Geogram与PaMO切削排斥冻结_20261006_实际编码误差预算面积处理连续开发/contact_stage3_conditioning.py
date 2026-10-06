"""自动读取原碰撞导数非有限接触，以几何折叠改善输入，完整求解函数保持。"""
from pathlib import Path
from datetime import datetime,timezone,timedelta
import json,hashlib,subprocess,inspect
import numpy as np,warp as wp
from pamo_safe_project import energy
from contact_conditioning_geometry import endpoint_collapse,bad_contact_edges

@wp.kernel
def find_bad_contact(d:wp.array(dtype=float),g:wp.array(dtype=wp.vec3,ndim=2),threshold:float,flags:wp.array(dtype=int)):
    i=wp.tid()
    if d[i]<threshold:
        for j in range(4):
            for k in range(3):
                if not wp.isfinite(g[i,j][k]):flags[i]=1

@wp.kernel
def gather_contacts(ids:wp.array(dtype=int),indices:wp.array(dtype=int,ndim=2),types:wp.array(dtype=int,ndim=2),oi:wp.array(dtype=int,ndim=2),ot:wp.array(dtype=int,ndim=2)):
    j=wp.tid();i=ids[j]
    for k in range(4):oi[j,k]=indices[i,k]
    for k in range(2):ot[j,k]=types[i,k]

def condition_stage3_input(system,register,gt_v,gt_f,vertices,faces,scale,output,checker):
    output=Path(output);output.mkdir(exist_ok=False);c=system.config
    from pamo_safe_project.kernels.distance_kernels import grad_funcs
    assert hashlib.sha256(Path(inspect.getfile(grad_funcs)).read_bytes()).hexdigest()=='f03880ab7108fd49fcd898bcd5124336712422c0f86502ded27b9e241bc885d5'
    assert hashlib.sha256(Path(inspect.getfile(energy)).read_bytes()).hexdigest()=='674a722a83e772f3a35c5a6ba069495936b546981f44ace9034a5f7810b11ce2'
    record={'生成时间':datetime.now(timezone(timedelta(hours=8))).isoformat(),'修改时间及修改内容':'首次生成，原碰撞失稳自动局部几何处理','文档概述':'不替换导数、不删接触；每次重新检测原接触，只有限数量几何折叠；非完整求解计数','索引目录':['probes','collapses'],'probes':[],'collapses':[],'status':'checking'}
    def save(): (output/'01-原碰撞失稳自动局部几何记录.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),'utf8')
    def probe(v,f):
        system.clear();register(gt_v,gt_f,v,f)
        q=system.q.numpy()[:system.n_particles]
        if system.do_nothing:raise RuntimeError('原第三阶段do_nothing，不能以跳过求解证明处理成功')
        system._update_vertex_target();wp.copy(system.q_prev_newton,system.q,count=system.n_particles);system._detect_contact()
        ec=system.energy_calcs[energy.CollisionBvhEnergyCalculator];system.energy.zero_();system.grad.zero_();system.hess_diag.zero_();ec.compute_energy(system.q,system.energy);ec.compute_diff(system.q,-1.0,system.grad,system.hess_diag)
        nc=int(ec.contact_counter.numpy()[0]);finite=bool(np.isfinite(system.energy.numpy()).all() and np.isfinite(system.grad.numpy()[:system.n_particles]).all() and np.isfinite(system.hess_diag.numpy()[:system.n_particles]).all());r={'contacts':nc,'collision_energy_gradient_diagonal_finite':finite,'contact_radius_changed':bool(ec.radius!=c.contact_detection_radius)}
        capture=output/f'probe_{len(record["probes"])}_actual.npz';np.savez_compressed(capture,q=q,faces=f);r['actual_q_faces_sha256']=hashlib.sha256(capture.read_bytes()).hexdigest()
        if r['contact_radius_changed']:raise RuntimeError('原接触容量触发半径缩小，当前几何处理拒绝')
        if finite:record['probes'].append(r);save();return q,[],[],0
        flags=wp.zeros(nc,dtype=int,device=system.device);wp.launch(find_bad_contact,dim=nc,inputs=[ec.d,ec.dd_dx,c.d_hat,flags],device=system.device);bad=np.flatnonzero(flags.numpy()).astype(np.int32);n=len(bad)
        if not n:raise RuntimeError('碰撞非有限但没有距离导数异常接触，当前几何机制不支持')
        ids=wp.array(bad,dtype=int,device=system.device);indices=wp.zeros((n,4),dtype=int,device=system.device);types=wp.zeros((n,2),dtype=int,device=system.device);wp.launch(gather_contacts,dim=n,inputs=[ids,ec.block_indices,ec.block_types,indices,types],device=system.device);ii,tt=indices.numpy(),types.numpy();r.update(bad_distance_derivative_contacts=n,bad_contact_indices=bad.tolist(),bad_point_indices=ii.tolist(),bad_contact_types=tt.tolist());record['probes'].append(r);save();return q,ii,tt,n
    try:
        q,ids,types,n=probe(vertices,faces);record['maximum_committed_collapses']=n;original_ids=np.arange(len(vertices));budget=n
        for step in range(budget):
            if not n:break
            accepted=False
            for edge in bad_contact_edges(ids,types,q):
                proposal,rec=endpoint_collapse(vertices,faces,edge,q,scale)
                if proposal is None:record.setdefault('rejected_proposals',[]).append(rec);continue
                vv,ff,qq=proposal;p=output/f'proposal_{step}.obj'
                with p.open('w',encoding='utf8') as stream:
                    for point in qq:stream.write('v '+' '.join(format(float(x),'.17g') for x in point)+'\n')
                    for face in ff:stream.write('f '+' '.join(str(int(x)+1) for x in face)+'\n')
                audit=json.loads(subprocess.run([str(checker),str(p)],check=True,capture_output=True,text=True).stdout);rec.update(embedding=audit,actual_encoded_sha256=hashlib.sha256(p.read_bytes()).hexdigest())
                if not audit['embedded_closed']:record.setdefault('rejected_proposals',[]).append(rec);continue
                next_q,next_ids,next_types,next_n=probe(vv,ff)
                assert np.array_equal(next_q,qq)
                if next_n>=n:raise RuntimeError('折叠后原异常接触数没有严格减少，当前提案拒绝')
                ids_map=np.asarray(rec.pop('remaining_original_vertex_ids'));rec['kept_input_vertex_id']=int(original_ids[rec['kept_original_vertex']]);rec['deleted_input_vertex_id']=int(original_ids[rec['deleted_original_vertex']]);original_ids=original_ids[ids_map];record['collapses'].append(rec);vertices,faces,q,ids,types,n=vv,ff,next_q,next_ids,next_types,next_n;accepted=True;save();break
            if not accepted:raise RuntimeError('原失稳接触没有原预算内合法短边提案')
        if n:raise RuntimeError('有限折叠预算后原碰撞导数仍非有限')
        record.update(status='completed_conditioning',retained_input_vertex_ids=original_ids.tolist(),final_vertices=len(vertices),final_faces=len(faces));save();return vertices,faces
    except Exception as error:record.update(status='rejected_with_recorded_evidence',error=repr(error));save();raise
