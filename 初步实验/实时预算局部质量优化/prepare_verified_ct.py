"""冻结另一研究线路实际保存并通过嵌入复审的CT16输入，记录适配成本。"""
import argparse
from datetime import datetime,timezone,timedelta
import hashlib
import json
from pathlib import Path
from time import perf_counter
import numpy as np
import trimesh
from benchmark import quality


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--record',type=Path,required=True);parser.add_argument('--root',type=Path,required=True)
    args=parser.parse_args();source=json.loads(args.record.read_text(encoding='utf-8'))
    events=source['routes'][0]['events'];assert source['routes'][0]['complete'] and len(events)==16
    args.root.mkdir(exist_ok=False);(args.root/'inputs').mkdir();cases=[]
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    previous=None
    for index,event in enumerate(events):
        assert event['status']=='published' and event['step']==index and event['exact_embedding']['embedded_closed']
        output=Path(event['output_path']);parent=Path(event['parent_path']);tool_path=Path(event['tool_path'])
        assert sha(output)==event['output_sha256'] and sha(parent)==event['parent_sha256'] and sha(tool_path)==event['tool_sha256']
        if previous:assert event['parent_sha256']==previous
        previous=event['output_sha256'];labels=output.with_name('candidate_labels.json')
        start=perf_counter();mesh=trimesh.load(output,process=False);tool=trimesh.load(tool_path,process=False)
        loaded=perf_counter();bits=np.array(json.loads(labels.read_text(encoding='utf-8'))['operand_bits'])
        assert len(bits)==len(mesh.faces) and quality(mesh.vertices,mesh.faces)['invalid']==0
        # 包围盒代理只选择允许维护的邻域，不将其称为真实切削区域或误差真值。
        a,b,c=(mesh.vertices[mesh.faces[:,k]] for k in range(3))
        low=np.minimum(np.minimum(a,b),c);high=np.maximum(np.maximum(a,b),c)
        active=np.all(high>=tool.vertices.min(0)-0.1,axis=1)&np.all(low<=tool.vertices.max(0)+0.1,axis=1)
        end=perf_counter();path=args.root/'inputs'/f'case{index:02d}.npz'
        np.savez(path,vertices=mesh.vertices,faces=mesh.faces,bits=bits,active=active)
        cases.append(dict(id=f'case{index:02d}',name=f'CT16保存状态第{index+1}刀',file=path.relative_to(args.root).as_posix(),sha256=sha(path),faces=len(mesh.faces),active_faces=int(active.sum()),
            source=str(output),source_sha256=event['output_sha256'],labels=str(labels),labels_sha256=sha(labels),tool=str(tool_path),tool_sha256=event['tool_sha256'],
            adapter_file_load_ms=(loaded-start)*1000,adapter_mask_and_validation_ms=(end-loaded)*1000,source_embedding=event['exact_embedding'],
            identity='已见实际反馈保存状态；后续追加维护不等于新算法连续反馈'))
    report=dict(time_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat(),source_record=str(args.record),source_record_sha256=sha(args.record),preparation_source_sha256=sha(Path(__file__)),
        protocol=dict(budgets_ms=[20,50,100,200],rounds=3,max_flips=16,guard='near',local_error_mm=1e-10,activity_proxy='与工具包围盒外扩0.1毫米相交的三角形',mask_preparation_excluded_from_static_maintenance_but_reported=True),cases=cases)
    (args.root/'02-合法CT保存输入与适配成本冻结.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(inputs=len(cases),active_faces=[x['active_faces'] for x in cases],not_own_feedback=True),ensure_ascii=False))


if __name__=='__main__':main()
