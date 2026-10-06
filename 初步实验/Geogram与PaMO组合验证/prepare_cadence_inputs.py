"""冻结开发与保留新轨迹，不根据任何维护输出挑选输入。"""
import argparse
import json
from pathlib import Path
import sys
import numpy as np
import trimesh
from locality_masks import save_obj_fp64
from run_geometry_study import now
from audit_followup_candidate import sha256

ASSETS=Path(__file__).resolve().parent.parent/'可复用磨削测试集'
sys.path.insert(0,str(ASSETS))
from prepare_feedback import make_route


def surface_route(mesh,name,count,split,rng,inputs,radius,source):
    path=inputs/(name+'.obj');save_obj_fp64(mesh,path)
    face=int(np.argmax(mesh.triangles_center[:,2]))
    normal=mesh.face_normals[face]
    tangent=mesh.triangles[face,1]-mesh.triangles[face,0]
    tangent=tangent/np.linalg.norm(tangent)
    side=np.cross(normal,tangent)
    anchor=mesh.triangles_center[face]
    angle=float(rng.uniform(0,2*np.pi))
    t=np.linspace(angle,angle+2.5*np.pi,count+1)
    points=anchor+radius*(0.65-0.12*np.linspace(0,1,count+1))[:,None]*normal
    points+=radius*0.6*(np.cos(t)[:,None]*tangent+np.sin(t)[:,None]*side)
    motion=dict(tool_radius_mm=radius,events=[dict(position_mm=p.tolist()) for p in points])
    route=make_route(dict(id=name),'渐深交叉',motion,path,inputs,split,source)
    route['source_anchor_face']=face
    return route


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    args.output.mkdir(exist_ok=False);inputs=args.output/'inputs';inputs.mkdir()
    rng=np.random.default_rng(2026100607)
    specifications=[('开发板体',trimesh.creation.box(extents=[6,6,4]),8,'development',0.55),
                    ('开发球体',trimesh.creation.icosphere(subdivisions=3,radius=3),8,'development',0.45),
                    ('保留板体',trimesh.creation.box(extents=[6.3,5.4,3.8]),12,'evaluation',0.51),
                    ('保留球体',trimesh.creation.icosphere(subdivisions=3,radius=3.2),12,'evaluation',0.43),
                    ('保留薄壁',trimesh.creation.box(extents=[5.8,5.2,0.3]),12,'evaluation',0.22),
                    ('保留贯通孔',trimesh.creation.annulus(r_min=0.8,r_max=3,height=1,sections=48),12,'evaluation',0.4)]
    routes=[surface_route(mesh,name,count,split,rng,inputs,radius,'synthetic_new_motion')
            for name,mesh,count,split,radius in specifications]
    public=ASSETS/'公开输入_BodyParts3D_v4'
    origin=json.loads((public/'01-公开来源清单.json').read_text(encoding='utf-8'))
    models={r['id']:r for r in origin['models']};selected=[]
    for line in (public/'原始资料/isa_element_parts.txt').read_text(encoding='utf-8-sig').splitlines():
        fields=line.split('\t')
        if len(fields)==3 and fields[1] in ('right scapula','right humerus'):
            selected.append((fields[1],models[fields[2]]))
    if len(selected)!=2:raise ValueError('公开器官映射不唯一，不替换输入')
    derivatives=[]
    for organ,row in sorted(selected):
        source=public/row['file']
        if sha256(source)!=row['sha256']:raise ValueError('公开原件摘要改变')
        raw=trimesh.load(source,process=False)
        unique,inverse=np.unique(raw.vertices,axis=0,return_inverse=True)
        mesh=trimesh.Trimesh(unique,inverse[raw.faces],process=False)
        center=mesh.bounds.mean(axis=0);scale=100/float(mesh.extents.max())
        mesh.vertices=(mesh.vertices-center)*scale
        name='公开新轨迹_'+row['id']
        routes.append(surface_route(mesh,name,12,'evaluation',rng,inputs,1.0,'public_atlas_seen_mesh_new_motion'))
        derivatives.append(dict(organ=organ,original_file=str(source),original_sha256=row['sha256'],
                                derived_sha256=routes[-1]['initial_mesh_sha256'],translation=(-center).tolist(),scale=scale,
                                units_note='人为100毫米测试尺度，非恢复解剖真实毫米；已见单图谱骨面上的新构造轨迹'))
    manifest=dict(time_beijing=now(),seed=2026100607,generator_sha256=sha256(Path(__file__)),routes=routes,
                  public_derivatives=derivatives,public_attribution=origin['attribution'],public_license=origin['license'],
                  units=dict(length='mm_explicit_test_scale',time='ms'),
                  scope='开发2路线16切削命令；保留6路线72命令；公开骨面已见、新轨迹未看维护输出；不是独立患者',
                  replay_policy=dict(late_event='reject',max_link_gap_ms=200),tool_discretization='subdivisions=3胶囊多面体，离散误差未认证')
    with (args.output/'01-完整范围冻结清单.json').open('x',encoding='utf-8') as stream:
        json.dump(manifest,stream,ensure_ascii=False,indent=2)
    print('开发16、保留72事件，',len(routes),'路线；全部输入与轨迹已冻结')
