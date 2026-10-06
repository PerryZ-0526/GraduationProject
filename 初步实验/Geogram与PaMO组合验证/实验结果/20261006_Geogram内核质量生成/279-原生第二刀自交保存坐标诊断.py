"""核对原版与候选实际自交面，记录来源点、准确平面符号和物理距离。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from fractions import Fraction
import hashlib
import json
import numpy as np
import trimesh

here=Path(__file__).resolve().parent
folder=here/'原生CT十六刀反馈全部实际输出'
record_path=folder/'01-原生CT十六刀反馈实际记录.json'
record=json.loads(record_path.read_text('utf8'))
assert record['status']=='completed_all_planned_events_with_rejections'
row=record['events'][1];assert row['status']=='rejected_native_output'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
parent_path=folder/Path(row['parent_path']).name;assert sha(parent_path)==row['parent_sha256']
tool_path=here/'原生CT十六刀开发冻结输入/01_tool.obj';assert sha(tool_path)==row['tool_sha256']
parent=trimesh.load(parent_path,process=False,force='mesh');tool=trimesh.load(tool_path,process=False,force='mesh')
parent_points={tuple(p) for p in np.asarray(parent.vertices)};tool_points={tuple(p) for p in np.asarray(tool.vertices)}

def exact_orientation(points):
    """四个保存双精度坐标直接转有理数，不将小非零体积判为零。"""
    p=[[Fraction(float(v)) for v in point] for point in points]
    a,b,c=[[p[j][d]-p[0][d] for d in range(3)] for j in [1,2,3]]
    value=a[0]*(b[1]*c[2]-b[2]*c[1])-a[1]*(b[0]*c[2]-b[2]*c[0])+a[2]*(b[0]*c[1]-b[1]*c[0])
    return {'sign':int((value>0)-(value<0)),'value':float(value)}

summary={'生成时间':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),
         '修改时间及修改内容':'首次诊断第二刀两个实际自交配对',
         '文档概述':'双方输出自交已证实；坐标尺度诊断不直接证明根因或修复有效',
         '索引目录':['methods'],'status':'running','source_record_sha256':sha(record_path),
         'parent_sha256':sha(parent_path),'tool_sha256':sha(tool_path),'methods':{}}
for method in ['baseline','candidate']:
    result=row['methods'][method];mesh_path=folder/Path(result['mesh_path']).name
    assert sha(mesh_path)==result['mesh_sha256']
    audit_path=folder/Path(result['audit']['path']).name;assert sha(audit_path)==result['audit']['sha256']
    audit=json.loads(json.loads(audit_path.read_text('utf8'))['stdout'])
    mesh=trimesh.load(mesh_path,process=False,force='mesh');vertices=np.asarray(mesh.vertices);faces=np.asarray(mesh.faces)
    pairs=[]
    for ids in audit['intersection_face_ids']:
        indices=[faces[i].tolist() for i in ids];triangles=[vertices[v] for v in indices]
        details=[]
        for t,other in [(triangles[0],triangles[1]),(triangles[1],triangles[0])]:
            normal=np.cross(t[1]-t[0],t[2]-t[0]);norm=np.linalg.norm(normal)
            details.append({'other_vertex_plane_distances_mm':((other-t[0])@(normal/norm)).tolist(),
                            'exact_plane_orientations':[exact_orientation([*t,p]) for p in other]})
        pairs.append({'face_ids':ids,'vertex_ids':indices,'triangles':[[p.tolist() for p in t] for t in triangles],
                      'shared_vertex_ids':sorted(set(indices[0])&set(indices[1])),
                      'vertex_sources':[['parent' if tuple(p) in parent_points else 'tool' if tuple(p) in tool_points else 'new' for p in t] for t in triangles],
                      'plane_diagnostics':details})
    summary['methods'][method]={'mesh_sha256':sha(mesh_path),'native_audit':audit,'pairs':pairs}
    print(method,[(p['face_ids'],p['shared_vertex_ids'],p['vertex_sources']) for p in pairs],flush=True)
summary.update(status='completed_same_parent_both_output_self_intersection_coordinate_diagnosis',
               finished_beijing=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'))
path=here/'280-原生第二刀自交保存坐标诊断结果.json';assert not path.exists()
path.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n','utf8')
