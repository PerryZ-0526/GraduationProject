"""只读诊断孔源差面在双精度中近乎共面、准确谓词却不共面的相邻面。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from fractions import Fraction
import hashlib
import json
import numpy as np
import trimesh

here=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
manifest_path=here/'18-原生十一同输入开发与速度运行前清单.json'
manifest=json.loads(manifest_path.read_text('utf8'))
def exact_coplanar(points):
    """按保存的双精度值转有理数，四点体积严格等于零才记为准确共面。"""
    p=[[Fraction(float(x)) for x in v] for v in points]
    a,b,c=[[p[i][d]-p[0][d] for d in range(3)] for i in [1,2,3]]
    return a[0]*(b[1]*c[2]-b[2]*c[1])-a[1]*(b[0]*c[2]-b[2]*c[0])+a[2]*(b[0]*c[1]-b[1]*c[0])==0
rows=[]
for i in [7,8]:
    case=manifest['cases'][i]
    for operand in ['parent','tool']:
        path=Path(case[operand]);assert sha(path)==case[operand+'_sha256']
        mesh=trimesh.load(path,process=False,force='mesh');vs=np.asarray(mesh.vertices);fs=np.asarray(mesh.faces);t=vs[fs]
        normals=np.cross(t[:,1]-t[:,0],t[:,2]-t[:,0]);lengths=np.linalg.norm(normals,axis=1)
        angles=[]
        for k in range(3):
            a,b=t[:,(k+1)%3]-t[:,k],t[:,(k+2)%3]-t[:,k]
            angles.append(np.degrees(np.arctan2(np.linalg.norm(np.cross(a,b),axis=1),np.einsum('ij,ij->i',a,b))))
        bad=(np.min(angles,axis=0)<10)&(lengths>0)
        index={}
        for f,tri in enumerate(fs):
            for k in range(3):index.setdefault(tuple(sorted((int(tri[k]),int(tri[(k+1)%3])))),[]).append(f)
        pairs=[];covered=set()
        for edge,neighbors in index.items():
            if len(neighbors)!=2:continue
            a,b=neighbors
            if not bad[a] or not bad[b]:continue
            na,nb=normals[a]/lengths[a],normals[b]/lengths[b]
            angle=float(np.degrees(np.arctan2(np.linalg.norm(np.cross(na,nb)),abs(float(na@nb)))))
            if angle>1e-5:continue
            vertices=sorted(set(map(int,fs[a]))|set(map(int,fs[b])))
            if len(vertices)!=4:continue
            points=vs[vertices];exact=exact_coplanar(points)
            residual=float(np.max(np.abs((points-t[a,0])@na)))
            extent=max(float(np.linalg.norm(points.max(axis=0)-points.min(axis=0))),float(np.max(np.abs(points))))
            # 保存普通浮点类型，使比较和诊断字段能直接序列化为JSON。
            margin=float(128*np.finfo(float).eps*extent)
            if residual<=margin:covered.update([a,b])
            pairs.append({'faces':[int(a),int(b)],'edge':list(edge),'vertices':vertices,
                          'normal_angle_degrees':angle,'plane_residual_mm':residual,
                          'machine_scale_margin_mm':margin,'within_machine_scale_margin':residual<=margin,
                          'exact_coplanar_on_saved_binary64':exact})
        row={'case_index':i,'operand':operand,'path':str(path),'source_sha256':sha(path),
             'bad_faces':int(bad.sum()),'near_coplanar_bad_pairs':len(pairs),
             'nonexact_near_pairs':sum(not p['exact_coplanar_on_saved_binary64'] for p in pairs),
             'bad_faces_with_machine_scale_coplanar_bad_neighbor':len(covered),'pairs':pairs}
        rows.append(row);print(i,operand,{k:row[k] for k in ['bad_faces','near_coplanar_bad_pairs','nonexact_near_pairs','bad_faces_with_machine_scale_coplanar_bad_neighbor']},flush=True)
record={'生成时间':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),
        '修改时间及修改内容':'孔源差面相邻共面精度只读诊断',
        '文档概述':'法线近似与准确体积分别报告，不自动当成可合并证书',
        '索引目录':['rows'],'status':'completed_four_source_mesh_coplanarity_precision_diagnoses',
        'input_manifest_sha256':sha(manifest_path),'rows':rows}
(here/'143-孔源差面相邻共面精度诊断结果.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n','utf8')
