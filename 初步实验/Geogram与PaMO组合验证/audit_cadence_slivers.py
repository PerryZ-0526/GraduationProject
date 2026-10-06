"""只读区分参照面积下限拒绝、保存坐标精确共线与极小非零面。"""
import argparse
from fractions import Fraction
import json
from pathlib import Path
import numpy as np
import trimesh
from audit_followup_candidate import sha256
from run_geometry_study import now,save


def exact_collinear(triangle):
    points=[[Fraction.from_float(float(c)) for c in point] for point in triangle]
    a=[points[1][i]-points[0][i] for i in range(3)]
    b=[points[2][i]-points[0][i] for i in range(3)]
    return all(a[i]*b[j]-a[j]*b[i]==0 for i,j in ((0,1),(0,2),(1,2)))


def run(batch):
    terminal=json.loads((batch/'03-批次环境与完整分母.json').read_text(encoding='utf-8'))
    if terminal['status']!='completed_with_recorded_outcomes':raise ValueError('完整批次尚未终态')
    rows=[]
    for folder in sorted(batch.glob('reference_*')):
        record=json.loads((folder/'01-独立累计工具参照.json').read_text(encoding='utf-8'))
        for position,item in enumerate(record['rows']):
            if item['status']!='reference_invalid':continue
            source=folder/f'step_{position}'/'source.obj'
            if sha256(source)!=item['source_sha256']:raise ValueError('无效参照保存字节改变')
            mesh=trimesh.load(source,process=False)
            indices=np.flatnonzero(mesh.area_faces<=1e-12)
            faces=[]
            for face in indices:
                triangle=mesh.triangles[face]
                faces.append(dict(face=int(face),area_fp64_mm2=float(mesh.area_faces[face]),
                    saved_coordinate_exact_collinear=exact_collinear(triangle),
                    maximum_edge_mm=float(np.linalg.norm(np.roll(triangle,-1,axis=0)-triangle,axis=1).max())))
            rows.append(dict(reference=folder.name,event=item['event'],source_sha256=sha256(source),
                area_floor_rejected_faces=len(indices),exact_collinear_faces=sum(f['saved_coordinate_exact_collinear'] for f in faces),faces=faces))
    report=dict(time_beijing=now(),area_floor_mm2=1e-12,rows=rows,ledger_sha256=sha256(batch/'04-逐刀真实父反馈记录.jsonl'),
        interpretation='有理精确共线仅针对保存二进制FP64坐标；非连续几何证书，不改变原接受或拒绝结果',script_sha256=sha256(Path(__file__)))
    save(batch/'07-近退化参照只读归因.json',report)
    print('无效参照只读归因',len(rows),'精确共线面',sum(r['exact_collinear_faces'] for r in rows))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batch',type=Path,required=True)
    run(parser.parse_args().batch)
