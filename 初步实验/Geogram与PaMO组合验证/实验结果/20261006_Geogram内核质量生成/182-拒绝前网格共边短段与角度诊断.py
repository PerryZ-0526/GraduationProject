"""分析实际未接受网格与准确分裂请求，区分机器尺度短段和真实尺寸失配。"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import ast
import hashlib
import json
import numpy as np
import trimesh

here=Path(__file__).resolve().parent
folder=here/'整体拒绝前实际共边诊断输出'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
record=json.loads((folder/'01-拒绝前对象实际运行记录.json').read_text('utf8'))
assert record['status']=='completed_two_actual_internal_proposal_captures'
for name,digest in record['files'].items():assert sha(folder/name)==digest
module=ast.parse((here/'04-原版生成阶段同输入基线.py').read_text('utf8'))
function=next(n for n in module.body if isinstance(n,ast.FunctionDef) and n.name=='quality')
scope={'np':np,'trimesh':trimesh}
exec(compile(ast.Module(body=[function],type_ignores=[]),'quality','exec'),scope)
summary={'生成时间':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),
         '修改时间及修改内容':'首次复算实际未接受对象与共边短段',
         '文档概述':'只读诊断，不将未接受对象算质量成果或预设失配原因',
         '索引目录':['cases'],'status':'running','cases':[]}
for i in [7,10]:
    path=folder/f'case{i:02d}_depth0.obj'
    mesh=trimesh.load(path,process=False,force='mesh')
    triangles=np.asarray(mesh.vertices)[np.asarray(mesh.faces)]
    minimum=np.full(len(triangles),180.0)
    lengths=[]
    for k in range(3):
        a=triangles[:,(k+1)%3]-triangles[:,k];b=triangles[:,(k+2)%3]-triangles[:,k]
        minimum=np.minimum(minimum,np.degrees(np.arctan2(np.linalg.norm(np.cross(a,b),axis=1),np.einsum('ij,ij->i',a,b))))
        lengths.append(np.linalg.norm(a,axis=1))
    shortest=np.min(lengths,axis=0);bad=minimum<10
    splits=folder/f'case{i:02d}_depth0_splits.txt'
    intervals=[];byedge=[]
    for line in splits.read_text('utf8').splitlines():
        fields=line.split();a,b=map(int,fields[:2])
        points={int(p.split(':')[0]):float(p.split(':')[1]) for p in fields[2:]}
        values=sorted([0.0,1.0]+list(points.values()))
        gaps=np.diff(values);intervals.extend(gaps.tolist())
        if len(gaps) and gaps.min()<1e-10:
            byedge.append({'vertices':[a,b],'minimum_parameter_interval':float(gaps.min()),'points':points})
    intervals=np.asarray(intervals)
    row={'case_index':i,'proposal_sha256':sha(path),'proposal_quality':scope['quality'](path),
         'returned_quality':scope['quality'](folder/f'case{i:02d}_returned.obj'),
         'bad_face_shortest_edge_quantiles_mm':{str(q):float(np.quantile(shortest[bad],q)) for q in [0,.1,.5,.9,1]},
         'bad_faces_short_edge_counts':{str(t):int(np.sum(bad & (shortest<=t))) for t in [1e-12,1e-9,1e-6,.0001,.001]},
         'split_interval_quantiles':{str(q):float(np.quantile(intervals,q)) for q in [0,.1,.5,.9,1]} if len(intervals) else {},
         'split_intervals_below_counts':{str(t):int(np.sum(intervals<=t)) for t in [1e-14,1e-12,1e-10,1e-6,.001,.01]},
         'machine_close_split_edges':byedge}
    summary['cases'].append(row)
    print(i,'proposal bad',row['proposal_quality']['below_10_faces'],'tiny intervals',row['split_intervals_below_counts'],flush=True)
summary.update(status='completed_two_actual_proposal_short_edge_diagnoses',
               finished_beijing=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'))
output=here/'183-拒绝前网格共边短段与角度诊断结果.json';assert not output.exists()
output.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n','utf8')
