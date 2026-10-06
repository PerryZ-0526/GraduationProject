"""检查修复后仍自交的面，区分短边可收缩与没有短边的浮点越面。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json
import numpy as np
import trimesh

here=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
cases=[('十二输入第二刀首重复',here/'第十七轮新边收缩原生十二输入全部输出/11/candidate_r00.obj',
        here/'第十七轮新边收缩原生十二输入全部输出/11/candidate_native_audit.json',
        here/'原生CT十六刀反馈全部实际输出/e00_candidate.obj'),
       ('原分组新边修复连续第二刀',here/'原分组新边修复原生CT十六刀全部实际输出/e01_candidate.obj',
        here/'原分组新边修复原生CT十六刀全部实际输出/e01_candidate_audit.json',
        here/'原分组新边修复原生CT十六刀全部实际输出/e00_candidate.obj')]
tool=trimesh.load(here/'原生CT十六刀开发冻结输入/01_tool.obj',process=False,force='mesh')
tool_points={tuple(p) for p in np.asarray(tool.vertices)}
output=here/'334-新边修复后自交邻域极短边诊断结果.json';assert not output.exists()
summary={'生成时间':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),
 '修改时间及修改内容':'首次新边修复后仍自交的邻域定位','文档概述':'只读诊断，不发布或移动点',
 '索引目录':['cases'],'status':'running','cases':[]}
for name,path,audit_path,parent_path in cases:
    wrapped=json.loads(audit_path.read_text('utf8'));audit=json.loads(wrapped['stdout'])
    if 'mesh_sha256' in wrapped:assert sha(path)==wrapped['mesh_sha256']
    mesh=trimesh.load(path,process=False,force='mesh');vertices=np.asarray(mesh.vertices);faces=np.asarray(mesh.faces)
    parent=trimesh.load(parent_path,process=False,force='mesh');original={tuple(p) for p in np.asarray(parent.vertices)}|tool_points
    bad_faces=sorted({f for pair in audit['intersection_face_ids'] for f in pair})
    bad_vertices={int(v) for f in bad_faces for v in faces[f]}
    pairs=[]
    for a,b in audit['intersection_face_ids']:
        distances=[(float(np.linalg.norm(vertices[v]-vertices[w])),int(v),int(w)) for v in faces[a] for w in faces[b] if v!=w]
        pairs.append({'face_ids':[a,b],'vertex_ids':[faces[a].tolist(),faces[b].tolist()],
             'minimum_nonshared_vertex_distance':min(distances),
             'coordinates':[[vertices[v].tolist() for v in faces[f]] for f in [a,b]]})
    edges={tuple(sorted((int(v),int(w)))) for f in faces for v,w in zip(f,np.roll(f,-1))}
    tiny=[]
    for v,w in sorted(edges):
        if v not in bad_vertices and w not in bad_vertices:continue
        p,q=vertices[v],vertices[w];distance=float(np.linalg.norm(p-q))
        bound=128*np.finfo(float).eps*max(float(np.abs(p).max()),float(np.abs(q).max()))
        if distance>bound:continue
        star_a={i for i,f in enumerate(faces) if v in f};star_b={i for i,f in enumerate(faces) if w in f}
        ring_a={int(x) for i in star_a for x in faces[i]}-{v,w}
        ring_b={int(x) for i in star_b for x in faces[i]}-{v,w}
        incident=star_a&star_b
        opposite={int(x) for i in incident for x in faces[i]}-{v,w}
        tiny.append({'vertices':[v,w],'length_mm':distance,'bound_mm':float(bound),
          'original':[tuple(p) in original,tuple(q) in original],
          'incident_faces':sorted(incident),'link_valid':len(incident)==2 and len(opposite)==2 and ring_a&ring_b==opposite})
    row={'name':name,'mesh_sha256':sha(path),'audit':audit,'pairs':pairs,'remaining_tiny_edges_in_bad_star':tiny}
    summary['cases'].append(row)
    print(name,'自交',audit['self_intersection_pairs'],'短边',tiny,flush=True)
summary.update(status='completed_read_only_remaining_bad_star_machine_edge_diagnosis')
output.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n','utf8')
