"""同一138段裁剪工具的Geogram诊断与逐步质量维护支线，质量失败后停止回灌。"""
from pathlib import Path
from datetime import datetime,timezone,timedelta
from time import perf_counter
import json
import hashlib
import subprocess
import argparse
from itertools import combinations
import numpy as np
import trimesh
import pymeshlab as pm
from run_comparison import export_double,quality,face_keys,stats
from experiment import load_candidate
from coverage_inputs import original_plan
from intersections import separated_xy

ROOT=Path(__file__).resolve().parent
BINARY='/root/autodl-tmp/graduation_project/cuda_stage0/geogram_plan_io'


def boolean(a,b,out,intersection=False):
    command=[BINARY]+(['--intersection'] if intersection else [])+[str(a),str(b),str(out)]
    with out.with_suffix('.log').open('w',encoding='utf-8') as log:
        subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,timeout=60,check=True)
    return trimesh.load(out,force='mesh',process=False)


def maintained(mesh,item,edge,original_keys=None):
    """直接使用MeshLab公开滤镜，无孔洞填补、Manifold重解释或面编号特判。"""
    ms=pm.MeshSet()
    if original_keys is None:
        ms.add_mesh(pm.Mesh(mesh.vertices,mesh.faces))
    else:
        # 竞争维护必须覆盖布尔实际改变的所有面，而非假设布尔只修改工具邻域。
        changed=np.array([key not in original_keys for key in face_keys(mesh)],dtype=float)
        if not changed.any():
            return mesh.copy()
        ms.add_mesh(pm.Mesh(mesh.vertices,mesh.faces,f_scalar_array=changed))
    ms.meshing_remove_duplicate_vertices()
    ms.meshing_remove_null_faces()
    center=(np.array(item['start'])+item['end'])/2
    radius=item['radius']+np.linalg.norm(np.array(item['end'])-item['start'])/2+1.2
    expression=' || '.join(f'(x{i}-({center[0]}))^2+(y{i}-({center[1]}))^2+(z{i}-({center[2]}))^2<{radius**2}' for i in range(3))
    ms.compute_selection_by_condition_per_face(condselect=expression if original_keys is None else 'fq > 0')
    ms.meshing_isotropic_explicit_remeshing(iterations=5,targetlen=pm.PureValue(edge),featuredeg=30.,
        checksurfdist=True,maxsurfdist=pm.PureValue(.025),selectedonly=True,smoothflag=True)
    output=ms.current_mesh()
    return trimesh.Trimesh(output.vertex_matrix(),output.face_matrix(),process=False)


def distances(a,b):
    """独立累计无维护分支仅用于维护漂移参照；抽样距离不冒充全域证书。"""
    reports=[]
    for source,target in [(a,b),(b,a)]:
        points,_=trimesh.sample.sample_surface(source,2048,seed=20260908)
        distance=trimesh.proximity.closest_point(target,points)[1]
        reports.append(stats(distance))
    return reports


def diagnose(mesh,keys):
    result=quality(mesh,keys)
    ms=pm.MeshSet()
    ms.add_mesh(pm.Mesh(mesh.vertices,mesh.faces))
    ms.compute_selection_by_self_intersections_per_face()
    flags=np.flatnonzero(ms.current_mesh().face_selection_array())
    result['self_intersection_flags']=len(flags)
    # 与局部方法相同的严格投影分离判据；过多报警不做二次方开销的排除，不冒充真实自交。
    cleared=not len(flags)
    if 2<=len(flags)<=32 and result['changed']['bad_faces']==0:
        triangles=mesh.triangles
        cleared=all(separated_xy(triangles[i],triangles[j]) for i,j in combinations(flags,2))
    result['flags_cleared_by_exact_projection']=bool(cleared)
    result['quality_gate']=bool(result['changed']['bad_faces']==0 and result['watertight'] and result['winding']
        and result['euler']==2 and result['nonmanifold_edges']==0 and cleared)
    return result


def main():
    global BINARY
    parser=argparse.ArgumentParser()
    parser.add_argument('--no-simplify',action='store_true')
    parser.add_argument('--maintain-changed',action='store_true')
    args=parser.parse_args()
    if args.no_simplify:
        BINARY='/root/autodl-tmp/graduation_project/cuda_stage0/geogram_plan_nosimplify'
    folder=ROOT/'强基线覆盖结果'/datetime.now(timezone(timedelta(hours=8))).strftime('%Y%m%d_%H%M%S')
    folder.mkdir(parents=True)
    candidate,_=load_candidate()
    plan=original_plan()
    result=dict(status='running',plan=plan,plan_sha256=hashlib.sha256(json.dumps(plan,sort_keys=True).encode()).hexdigest(),
                binary_sha256=hashlib.sha256(Path(BINARY).read_bytes()).hexdigest(),raw=[],maintenance={'0.4':[],'0.6':[]},
                formal_full_certificate=False,no_simplify=args.no_simplify,maintain_changed=args.maintain_changed)
    def save():
        (folder/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    initial=folder/'initial.obj'
    initial.write_text(export_double(candidate['whole']),encoding='utf-8')
    keys=set(face_keys(candidate['whole']))
    previous=initial
    branches={edge:initial for edge in result['maintenance']}
    sphere=trimesh.creation.icosphere(subdivisions=3,radius=1.)
    result['tool_subdivision']=3
    result['initial']=diagnose(candidate['whole'],keys)
    save()
    try:
        for item in plan:
            step=item['step']
            started=perf_counter()
            a,b=np.array(item['start']),np.array(item['end'])
            capsule=trimesh.convex.convex_hull(np.vstack([sphere.vertices*item['radius']+a,sphere.vertices*item['radius']+b]))
            rawtool,clip,tool,out=[folder/f'{name}_{step}.obj' for name in ['sweep','clip','tool','raw']]
            rawtool.write_text(export_double(capsule),encoding='utf-8')
            cylinder=trimesh.creation.cylinder(radius=item['clip_radius'],sections=128,segment=[[0,0,-20],[0,0,20]])
            clip.write_text(export_double(cylinder),encoding='utf-8')
            boolean(rawtool,clip,tool,True)
            raw=boolean(previous,tool,out)
            row=dict(step=step,phase=item['phase'],**diagnose(raw,keys),elapsed_ms=(perf_counter()-started)*1000)
            # 此支线只诊断未维护算法，可继续回灌坏质量；不计为合格发布。
            result['raw'].append(row)
            for edge,path in list(branches.items()):
                begin=perf_counter()
                attempt=dict(step=step,phase=item['phase'],accepted=False)
                result['maintenance'][edge].append(attempt)
                try:
                    proposed=raw if path==previous else boolean(path,tool,folder/f'maint_input_{edge}_{step}.obj')
                    output=maintained(proposed,item,float(edge),original_keys=keys if args.maintain_changed else None)
                    output_path=folder/f'maint_{edge}_{step}.obj'
                    output_path.write_text(export_double(output),encoding='utf-8')
                    attempt.update(diagnose(output,keys))
                    attempt['sampled_drift']=distances(output,raw)
                    attempt['accepted']=bool(attempt['quality_gate'] and max(d['max'] for d in attempt['sampled_drift'])<=.075)
                    if attempt['accepted']:
                        branches[edge]=output_path
                    else:
                        del branches[edge]
                except Exception as exc:
                    attempt['error']=str(exc)
                    del branches[edge]
                attempt['elapsed_ms']=(perf_counter()-begin)*1000
            previous=out
            save()
            print('geogram',step,item['phase'],'changed bad',row['changed']['bad_faces'],'maintenance active',list(branches),flush=True)
        result['status']='completed'
    except Exception as exc:
        result['status'],result['error']='failed',str(exc)
        raise
    finally:
        result['raw_unexecuted']=138-len(result['raw'])
        save()
        print(folder,flush=True)


if __name__=='__main__':
    main()
