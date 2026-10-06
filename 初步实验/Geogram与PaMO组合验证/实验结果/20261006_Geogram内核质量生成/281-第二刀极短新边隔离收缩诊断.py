"""只对已失败保存对象作单边机理诊断，不作为原生生成成功或连续发布。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json
import numpy as np
import trimesh

here=Path(__file__).resolve().parent
source=here/'原生CT十六刀反馈全部实际输出/e01_candidate.obj'
parent=here/'原生CT十六刀反馈全部实际输出/e00_candidate.obj'
tool=here/'原生CT十六刀开发冻结输入/01_tool.obj'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
mesh=trimesh.load(source,process=False,force='mesh');vertices=np.asarray(mesh.vertices);faces=np.asarray(mesh.faces)
a,b=21973,21974
ma=(faces==a).any(axis=1);mb=(faces==b).any(axis=1)
opposite=set(faces[ma&mb].reshape(-1))-{a,b};common=(set(faces[ma].reshape(-1))&set(faces[mb].reshape(-1)))-{a,b}
assert int((ma&mb).sum())==2 and len(opposite)==2 and common==opposite
source_points=set()
for path in [parent,tool]:
    original=trimesh.load(path,process=False,force='mesh');source_points.update(map(tuple,np.asarray(original.vertices)))
assert tuple(vertices[a]) not in source_points and tuple(vertices[b]) not in source_points
length=float(np.linalg.norm(vertices[a]-vertices[b]));margin=128*np.finfo(float).eps*float(np.max(np.abs(vertices[[a,b]])))
assert length<=margin
updated=faces.copy();updated[updated==b]=a
deleted=np.any(np.diff(np.sort(updated,axis=1),axis=1)==0,axis=1)
affected=mb&~deleted
before=vertices[faces[affected]];after=vertices[updated[affected]]
old_normals=np.cross(before[:,1]-before[:,0],before[:,2]-before[:,0]);new_normals=np.cross(after[:,1]-after[:,0],after[:,2]-after[:,0])
dots=np.einsum('ij,ij->i',old_normals,new_normals)
assert np.all(dots>0) and np.all(np.linalg.norm(new_normals,axis=1)>0)
output=here/'282-第二刀单边隔离诊断网格.obj';assert not output.exists()
with output.open('x',encoding='ascii') as stream:
    for v in vertices:stream.write('v '+' '.join(format(float(x),'.17g') for x in v)+'\n')
    for f in updated[~deleted]:stream.write('f '+' '.join(str(int(v)+1) for v in f)+'\n')
now=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
record={'生成时间':now,'修改时间及修改内容':now+'，首次隔离单条极短新边收缩',
        '文档概述':'外部保存对象诊断，不发布，不伪称Geogram内核已修复',
        '索引目录':['edge','checks'],'status':'completed_single_edge_geometric_topology_probe_not_native_audited',
        'source_sha256':sha(source),'parent_sha256':sha(parent),'tool_sha256':sha(tool),
        'edge':[a,b],'length_mm':length,'machine_margin_mm':margin,'removed_faces':int(deleted.sum()),
        'affected_retained_faces':int(affected.sum()),'all_retained_normals_same_orientation':bool(np.all(dots>0)),
        'both_vertices_new':True,'retained_vertex_coordinates_unchanged':True,'output_sha256':sha(output)}
path=here/'283-第二刀单边隔离收缩诊断记录.json';assert not path.exists()
path.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n','utf8')
print(json.dumps(record,ensure_ascii=False))
