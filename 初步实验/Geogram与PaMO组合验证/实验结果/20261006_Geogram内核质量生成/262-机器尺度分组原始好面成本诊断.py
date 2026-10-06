"""只读核对近共面新增分组中有多少原始好面，决定是否值得增加质量筛选。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from fractions import Fraction
import hashlib
import json
import numpy as np
import trimesh

here=Path(__file__).resolve().parent
manifest_path=here/'18-原生十一同输入开发与速度运行前清单.json'
manifest=json.loads(manifest_path.read_text('utf8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
summary={'生成时间':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),
         '修改时间及修改内容':'首次核对原始好面是否参与机器尺度新增分组',
         '文档概述':'只读源面诊断，不假定新增分组就是速度瓶颈','索引目录':['rows'],
         'status':'running','manifest_sha256':sha(manifest_path),'rows':[]}
for i in [0,3,7,9,10]:
    for operand in ['parent','tool']:
        case=manifest['cases'][i];path=Path(case[operand]);assert sha(path)==case[operand+'_sha256']
        mesh=trimesh.load(path,process=False,force='mesh');vertices=np.asarray(mesh.vertices);faces=np.asarray(mesh.faces)
        triangles=vertices[faces];cross=np.cross(triangles[:,1]-triangles[:,0],triangles[:,2]-triangles[:,0])
        norms=np.linalg.norm(cross,axis=1);normals=np.divide(cross,norms[:,None],out=np.zeros_like(cross),where=norms[:,None]>0)
        minimum=np.full(len(faces),180.)
        for k in range(3):
            a=triangles[:,(k+1)%3]-triangles[:,k];b=triangles[:,(k+2)%3]-triangles[:,k]
            minimum=np.minimum(minimum,np.degrees(np.arctan2(np.linalg.norm(np.cross(a,b),axis=1),np.einsum('ij,ij->i',a,b))))
        adjacency=np.asarray(mesh.face_adjacency);edges=np.asarray(mesh.face_adjacency_edges)
        na,nb=normals[adjacency[:,0]],normals[adjacency[:,1]]
        angles=np.degrees(np.arctan2(np.linalg.norm(np.cross(na,nb),axis=1),np.abs(np.einsum('ij,ij->i',na,nb))))
        rows=[]
        for pair_index in np.flatnonzero(angles<=1e-5):
            fa,fb=map(int,adjacency[pair_index]);edge=edges[pair_index]
            if norms[fa]==0 or norms[fb]==0:continue
            oa=next(int(v) for v in faces[fa] if v not in edge);ob=next(int(v) for v in faces[fb] if v not in edge)
            corners=vertices[[int(edge[0]),oa,int(edge[1]),ob]]
            residual=max(float(np.max(np.abs((corners-triangles[fa,0])@normals[fa]))),float(np.max(np.abs((corners-triangles[fb,0])@normals[fb]))))
            scale=max(float(np.max(np.abs(corners))),float(np.max(np.linalg.norm(corners-triangles[fa,0],axis=1))))
            if residual>128*np.finfo(float).eps*scale:continue
            turns=[];valid=True
            for k in range(4):
                a=corners[(k+3)%4]-corners[k];b=corners[(k+1)%4]-corners[k]
                if np.degrees(np.arctan2(np.linalg.norm(np.cross(a,b)),a@b))<20:valid=False;break
                turns.append(float(np.cross(b,corners[(k+2)%4]-corners[(k+1)%4])@normals[fa]))
            if not valid or any(t==0 for t in turns) or min(turns)*max(turns)<=0:continue
            # 四个保存双精度点用有理数精确求体积，区分原版准确共面与本次机器尺度新增合并。
            p=[[Fraction(float(v)) for v in point] for point in corners]
            a,b,c=[[p[j][d]-p[0][d] for d in range(3)] for j in [1,2,3]]
            determinant=a[0]*(b[1]*c[2]-b[2]*c[1])-a[1]*(b[0]*c[2]-b[2]*c[0])+a[2]*(b[0]*c[1]-b[1]*c[0])
            if determinant==0:continue
            rows.append({'faces':[fa,fb],'bad_source_present':bool(minimum[fa]<10 or minimum[fb]<10),
                         'minimum_angles':[float(minimum[fa]),float(minimum[fb])]})
        item={'case_index':i,'operand':operand,'source_sha256':sha(path),'source_faces':len(faces),
              'near_machine_quad_nonexact_pairs':len(rows),'with_bad_source_face':sum(r['bad_source_present'] for r in rows),
              'both_original_faces_good':sum(not r['bad_source_present'] for r in rows),'pairs':rows}
        summary['rows'].append(item);print(i,operand,len(rows),item['both_original_faces_good'],flush=True)
summary.update(status='completed_ten_source_machine_quad_quality_cost_diagnoses',
               finished_beijing=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'))
path=here/'263-机器尺度分组原始好面成本诊断结果.json';assert not path.exists()
path.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n','utf8')
