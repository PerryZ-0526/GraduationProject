"""只读定位剩余小角的边界约束及CT零面；不据近共面诊断作准确几何保证。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from collections import Counter
from fractions import Fraction
import hashlib
import json
import numpy as np
import trimesh

here=Path(__file__).resolve().parent
quality_path=here/'25-原生十一同输入质量几何与速度复算.json'
quality=json.loads(quality_path.read_text('utf8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
rows=[]
for i,case in enumerate(quality['cases']):
    path=here/'原生同输入全部重复输出'/f'{i:02d}'/'candidate_r00.obj'
    mesh=trimesh.load(path,process=False,force='mesh')
    vertices=np.asarray(mesh.vertices);faces=np.asarray(mesh.faces);triangles=vertices[faces]
    cross=np.cross(triangles[:,1]-triangles[:,0],triangles[:,2]-triangles[:,0])
    twice_area=np.linalg.norm(cross,axis=1)
    normals=np.divide(cross,twice_area[:,None],out=np.zeros_like(cross),where=twice_area[:,None]>0)
    edges={}
    for f,face in enumerate(faces):
        for k in range(3): edges.setdefault(tuple(sorted([int(face[k]),int(face[(k+1)%3])])),[]).append(f)
    angles=[]
    for k in range(3):
        a,b=triangles[:,(k+1)%3]-triangles[:,k],triangles[:,(k+2)%3]-triangles[:,k]
        angles.append(np.degrees(np.arctan2(np.linalg.norm(np.cross(a,b),axis=1),np.einsum('ij,ij->i',a,b))))
    angles=np.asarray(angles).T
    bad=np.flatnonzero((angles.min(axis=1)<10)&(twice_area>0))
    corner_types=Counter();lengths={0:[],1:[],2:[]};areas={0:0.0,1:0.0,2:0.0}
    for f in bad:
        k=int(np.argmin(angles[f]));v=int(faces[f,k]);constrained=0
        for j in [(k+1)%3,(k+2)%3]:
            adjacent=edges[tuple(sorted([v,int(faces[f,j])]))]
            neighbors=[g for g in adjacent if g!=f]
            same_plane=False
            if len(neighbors)==1:
                g=neighbors[0]
                cosine=float(np.dot(normals[f],normals[g]))
                residual=float(np.abs((triangles[g]-triangles[f,0])@normals[f]).max())
                same_plane=cosine>1-1e-12 and residual<=1e-10
            constrained+=int(not same_plane)
        corner_types[constrained]+=1
        lengths[constrained].append(float(np.linalg.norm(triangles[f,1]-triangles[f,0])))
        areas[constrained]+=float(twice_area[f]/2)
    invalid=[]
    for f in np.flatnonzero(twice_area==0):
        points=triangles[f]
        a,b,c=[[Fraction.from_float(float(x)) for x in p] for p in points]
        ab=[b[k]-a[k] for k in range(3)];ac=[c[k]-a[k] for k in range(3)]
        exact=[ab[1]*ac[2]-ab[2]*ac[1],ab[2]*ac[0]-ab[0]*ac[2],ab[0]*ac[1]-ab[1]*ac[0]]
        invalid.append({'face_id':int(f),'vertex_ids':faces[f].tolist(),'coordinates_mm':points.tolist(),
                        'distinct_coordinate_count':len(set(tuple(p) for p in points)),
                        'edge_lengths_mm':[float(np.linalg.norm(points[(k+1)%3]-points[k])) for k in range(3)],
                        'stored_exact_collinear':all(x==0 for x in exact)})
    row={'case':case['case'],'output_sha256':sha(path),'bad_count':len(bad),
         'minimum_angle_incident_constraint_edges':dict(corner_types),
         'bad_area_by_constraint_edges_mm2':areas,'zero_faces':invalid}
    rows.append(row)
    print(case['case'],'小角两边约束计数',dict(corner_types),'零面',len(invalid),flush=True)
out={'生成时间':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),
     '修改时间及修改内容':'首次剩余差面边界与CT零面准确坐标诊断',
     '文档概述':'相邻面的近共面只用于原因筛查；零面准确叉积针对保存双精度坐标',
     '索引目录':['rows'],'status':'completed_remaining_sliver_constraint_and_zero_coordinate_diagnosis',
     'source_quality_sha256':sha(quality_path),'plane_probe_limits':{'normal_cosine_gap':1e-12,'distance_mm':1e-10},'rows':rows}
(here/'33-剩余差面边界与CT零面坐标诊断.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n','utf8')
