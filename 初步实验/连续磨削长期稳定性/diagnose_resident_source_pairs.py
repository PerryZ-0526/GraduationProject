"""对实际拒绝源逐阶段重放已记录操作，定位精确相交面及其构造来源。"""
from collections import Counter
from datetime import datetime, timezone, timedelta
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import numpy as np
import trimesh


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    root,output=map(Path,sys.argv[1:3]);output.mkdir(exist_ok=False)
    sys.path.insert(0,str(root/'workers'));sys.path.insert(0,str(root))
    from covered_zero_cleanup import clean_arrays
    from resident_source_cleanup import cancel_opposed_index_faces
    from short_edge_repair import repair_short_edges
    from native_guard import separated_native
    from exact_mesh_memory import ExactMeshMemory
    full=ExactMeshMemory()
    candidate_path=Path(__file__).with_name('resident_source_cleanup_candidate.py')
    if '--cluster-repair' in sys.argv:
        spec=importlib.util.spec_from_file_location('cluster_candidate',candidate_path)
        candidate=importlib.util.module_from_spec(spec);spec.loader.exec_module(candidate)
    source=Path(__file__).with_name('exact_mesh_pairs.cpp');binary=output/'exact_mesh_pairs'
    argv=['g++','-std=c++17','-O2','-DNDEBUG','-DCGAL_DISABLE_GMP','-fno-fast-math','-ffp-contract=off',
          '-frounding-math',str(source),'-o',str(binary)]
    result=subprocess.run(argv,capture_output=True,text=True)
    (output/'01-编译日志.txt').write_text(result.stdout+result.stderr,encoding='utf-8')
    if result.returncode:raise RuntimeError('精确面定位器编译失败，原现场保留')
    records=[];report=json.loads((root/'02-常驻长序列完整记录.json').read_text())
    for run in report['runs']:
        folder=Path(run['output']);ledger_path=folder/'01-真实父反馈四预算完整记录.json'
        ledger=json.loads(ledger_path.read_text())
        event=next(e for e in ledger['routes'][0]['events'] if e['status']=='source_rejected')
        step=event['step'];raw_path=folder/f'e{step:03d}_raw.npz';final_path=folder/f'e{step:03d}_source.npz'
        with np.load(raw_path) as data:v,f,bits=[data[k].copy() for k in ('vertices','faces','bits')]
        stages=[('raw',v,f,bits,np.arange(len(f)))];raw_ids=np.arange(len(f))
        if event.get('cleanup'):
            v,f,bits,cleanup=clean_arrays(v,f,bits)
            raw_ids=np.asarray(cleanup['surviving_original_face_ids'])
            if raw_ids.tolist()!=event['cleanup']['surviving_original_face_ids']:raise ValueError('清理重放面号不一致')
            stages.append(('cleaned',v,f.copy(),bits.copy(),raw_ids.copy()))
        # 严格使用当时提交的操作及面号，不用新的时间预算重新选择收缩。
        changed=set();live=np.ones(len(f),dtype=bool);f=f.copy()
        for operation in event['repair']['operations']:
            ids=np.asarray(operation['changed_original_faces']);sub=f[ids].copy()
            sub[sub==operation['drop']]=operation['keep'];f[ids]=sub
            live[operation['removed_original_faces']]=False
            changed.update(raw_ids[ids].tolist())
        f,bits,raw_ids=f[live],bits[live],raw_ids[live]
        stages.append(('repaired_before_cancellation',v,f.copy(),bits.copy(),raw_ids.copy()))
        v,f,bits,cancellation=cancel_opposed_index_faces(v,f,bits)
        deleted={i for pair in cancellation['removed_opposed_face_pairs'] for i in pair}
        raw_ids=raw_ids[[i not in deleted for i in range(len(raw_ids))]]
        with np.load(final_path) as data:
            if not all(np.array_equal(a,data[k]) for a,k in zip((v,f,bits),('vertices','faces','bits'))):
                raise ValueError('逐操作重放没有重现实际拒绝数组')
        stages.append(('source',v,f,bits,raw_ids));stage_records=[]
        for name,v,f,bits,orig in stages:
            prefix=output/(folder.name+'_'+name);obj=prefix.with_suffix('.obj');pairs_path=prefix.with_suffix('.json')
            with obj.open('x',encoding='utf-8') as stream:
                for point in v:stream.write('v '+' '.join(format(float(x),'.17g') for x in point)+'\n')
                for tri in f:stream.write('f '+' '.join(str(int(x)+1) for x in tri)+'\n')
            check=subprocess.run([str(binary),str(obj),str(pairs_path)],capture_output=True,text=True)
            if check.returncode:raise RuntimeError('精确面定位器执行失败：'+check.stderr[:1500])
            metrics=json.loads(check.stdout);pairs=json.loads(pairs_path.read_text())['intersection_face_pairs'] if pairs_path.exists() else []
            pair_rows=[]
            for a,b in pairs:
                points=v[f[[a,b]]];edges=points[:,[1,2,0]]-points
                lengths=np.linalg.norm(edges,axis=2);areas=np.linalg.norm(np.cross(edges[:,0],-edges[:,2]),axis=1)/2
                # 原始阶段可能含全零边退化面，高度记零，避免诊断JSON出现NaN。
                altitudes=np.divide(2*areas,lengths.max(axis=1),out=np.zeros_like(areas),where=lengths.max(axis=1)>0)
                delta=np.linalg.norm(points[0,:,None,:]-points[1,None,:,:],axis=2)
                positive=delta[delta>0]
                pair_rows.append(dict(face_ids=[a,b],original_raw_face_ids=orig[[a,b]].tolist(),
                    touches_recorded_repair=bool(set(orig[[a,b]])&changed),vertex_ids=f[[a,b]].tolist(),
                    shared_vertex_ids=sorted(map(int,set(f[a])&set(f[b]))),source_bits=bits[[a,b]].tolist(),
                    areas_mm2=areas.tolist(),minimum_altitudes_mm=altitudes.tolist(),
                    minimum_edge_mm=lengths.min(axis=1).tolist(),
                    nearest_distinct_vertices_mm=float(positive.min()) if len(positive) else None,
                    vertices_mm=points.tolist()))
            stage_records.append(dict(stage=name,obj_sha256=sha(obj),metrics=metrics,pairs=pair_rows))
            print(json.dumps(dict(run=folder.name,stage=name,metrics=metrics),ensure_ascii=False),flush=True)
        limits=[];clusters=[]
        if ('--repair-limits' in sys.argv or '--cluster-repair' in sys.argv) and not run['reference']:
            with np.load(folder/f'e{step-1:03d}_output.npz') as data:parent=data['vertices'].copy()
        if '--repair-limits' in sys.argv and not run['reference']:
            # 单独放大隔离修复时间；不改来源、锚点、链接、覆盖和分离守卫，不发布诊断对象。
            for stage_name in ('raw','source'):
                sv,sf,sb=next((a,b,c) for n,a,b,c,_ in stages if n==stage_name)
                if stage_name=='raw' and event.get('cleanup'):sv,sf,sb,_=clean_arrays(sv,sf,sb)
                nv,nf,nb,repair=repair_short_edges(sv,sf,sb,parent,2000,max_collapses=len(sf)//2,separation_check=separated_native)
                nv,nf,nb,cancel=cancel_opposed_index_faces(nv,nf,nb);audit=full.audit(nv,nf)
                path=output/(folder.name+'_'+stage_name+'_2000ms.npz')
                np.savez_compressed(path,vertices=nv,faces=nf,bits=nb)
                row=dict(start_stage=stage_name,diagnostic_budget_ms=2000,published=False,
                    repair=repair,cancellation=cancel,full_audit=audit,output_sha256=sha(path))
                limits.append(row)
                print(json.dumps(dict(run=folder.name,start_stage=stage_name,diagnostic_budget_ms=2000,
                    repair_ms=repair['total_elapsed_ms'],operations=len(repair['operations']),
                    rejections=dict(Counter(repair['rejections'])),full_audit=audit),ensure_ascii=False),flush=True)
        if '--cluster-repair' in sys.argv and not run['reference']:
            # 预先固定两个额外开发尺度；全部负结果保留，不更换失败输入或冒充独立评价。
            tolerances=(1e-10,5e-9,1e-8) if '--cluster-scale-trials' in sys.argv else (1e-10,)
            for tolerance in tolerances:
                nv,nf,nb,proposal=candidate.repair_short_edge_clusters(v,f,bits,parent,tolerance_mm=tolerance)
                audit=full.audit(nv,nf);path=output/(folder.name+f'_cluster_{tolerance:g}.npz')
                np.savez_compressed(path,vertices=nv,faces=nf,bits=nb)
                clusters.append(dict(published=False,tolerance_mm=tolerance,proposal=proposal,full_audit=audit,output_sha256=sha(path),
                    candidate_source_sha256=sha(candidate_path)))
                print(json.dumps(dict(run=folder.name,tolerance_mm=tolerance,cluster_candidate=proposal['candidate'],
                    clusters=len(proposal['operations']),removed_faces=proposal.get('removed_faces'),
                    proposal_ms=proposal['total_elapsed_ms'],reason=proposal['reason'],full_audit=audit),ensure_ascii=False),flush=True)
            if '--active-anchor-trials' in sys.argv:
                manifest=json.loads((root/'manifest.json').read_text())
                route=next(r for r in manifest['routes'] if r['id']==run['route'])
                initial=trimesh.load(root/'inputs'/route['initial_mesh'],process=False).vertices
                tool_path=root/'inputs'/route['prefix_tools'][step]['mesh']
                if sha(tool_path)!=event['tool_sha256']:raise ValueError('活动域工具摘要不符')
                tool=trimesh.load(tool_path,process=False).vertices;low,high=tool.min(0),tool.max(0)
                outside=np.any((parent<low)|(parent>high),axis=1)
                # 仅作隔离诊断：保留所有初态点和工具盒外父点，观察旧切削内部点锁定的影响。
                anchors=np.vstack((initial,parent[outside]));tolerance=json.loads((root/'run_config.json').read_text()).get('cluster_tolerance_mm',1e-10)
                nv,nf,nb,proposal=candidate.repair_short_edge_clusters(v,f,bits,anchors,tolerance_mm=tolerance)
                audit=full.audit(nv,nf);path=output/(folder.name+'_active_anchor_trial.npz')
                np.savez_compressed(path,vertices=nv,faces=nf,bits=nb)
                clusters.append(dict(published=False,anchor_policy='原初态点与原扫掠工具包围盒外父点固定；仅隔离诊断',
                    tool_sha256=sha(tool_path),tool_low_mm=low.tolist(),tool_high_mm=high.tolist(),
                    original_parent_vertices=len(parent),fixed_outside_parent_vertices=int(outside.sum()),
                    tolerance_mm=tolerance,proposal=proposal,full_audit=audit,output_sha256=sha(path),candidate_source_sha256=sha(candidate_path)))
                print(json.dumps(dict(run=folder.name,trial='active_anchors',tolerance_mm=tolerance,
                    clusters=len(proposal['operations']),reason=proposal['reason'],proposal_ms=proposal['total_elapsed_ms'],full_audit=audit),ensure_ascii=False),flush=True)
        records.append(dict(route=run['route'],reference=run['reference'],step=step+1,
            ledger_sha256=sha(ledger_path),raw_npz_sha256=sha(raw_path),source_npz_sha256=sha(final_path),
            replay_matches_actual_source=True,repair_rejections=dict(Counter(event['repair']['rejections'])),
            stages=stage_records,isolated_repair_limits=limits,isolated_cluster_repair=clusters))
    out=dict(time_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat(),
        source_run_binding_sha256=sha(root/'01-常驻长序列运行绑定.json'),diagnostic_sha256=sha(__file__),
        checker_source_sha256=sha(source),checker_binary_sha256=sha(binary),compile_argv=argv,records=records,
        caveat='精确谓词针对保存的二进制FP64坐标；高度和端点距离是诊断量，不代表相交穿透深度。')
    (output/'02-逐阶段精确相交面归因.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':main()
