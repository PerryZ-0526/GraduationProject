"""合法CT数组维护配对对照，包含活动域与数值有效性适配，保留实际GPU同步。"""
import argparse
from datetime import datetime,timezone,timedelta
import hashlib
import json
from pathlib import Path
import subprocess
import numpy as np
from benchmark import quality,save_obj
from budget_flip import CpuScorer,TorchScorer
from local_guard import LocalGuard
from maintain_input import maintain_input
import maintain_input as input_api
from numeric_input import check_and_boxes as range_check
from numeric_input_reference import check_and_boxes as reference_check
from resumable_budget_flip import ResumableBudgetFlipState
from targeted_budget_flip import TargetedBudgetFlipState


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True);parser.add_argument('--backend',choices=('cpu','cuda'),required=True);parser.add_argument('--checker',required=True)
    args=parser.parse_args();root=args.root;sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    manifest=json.loads((root/'02-输入与研究预算冻结.json').read_text(encoding='utf-8'));freeze=json.loads((root/'03-执行源码冻结.json').read_text(encoding='utf-8'))
    for name,h in freeze.items():assert sha(root/name)==h
    out=root/args.backend;out.mkdir(exist_ok=False);rows=[];sources=[];controls=[];observations=[]
    def save(status):
        report=dict(time_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat(),status=status,backend=args.backend,source_sha256=freeze,manifest_sha256=sha(root/'02-输入与研究预算冻结.json'),rows=rows,sources=sources,controls=controls,gpu_observations=observations)
        temporary=out/'record.tmp';temporary.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');temporary.replace(out/'01-完整准备预算与保存对象记录.json')
    for case in manifest['cases']:
        path=root/case['file'];assert sha(path)==case['sha256'];data=np.load(path)
        v,f,bits,active=[data[k] for k in ('vertices','faces','bits','active')]
        low,high=data['tool_low'],data['tool_high']
        source=out/f'{case["id"]}_source.obj';save_obj(source,v,f)
        result=subprocess.run([args.checker,str(source)],capture_output=True,text=True,timeout=120)
        entry=dict(case=case['id'],returncode=result.returncode,stdout=result.stdout,stderr=result.stderr);sources.append(entry)
        before=quality(v,f)
        assert result.returncode==0 and json.loads(result.stdout)['embedded_closed'] and before['invalid']==0
        # 只比较目标队列实际访问的候选；小角优先本来就会改变队列次序。
        full=ResumableBudgetFlipState(v,f,bits,active,'cpu',LocalGuard);target=TargetedBudgetFlipState(v,f,bits,active,'cpu',LocalGuard)
        equal=all(target._candidate(e)==full._candidate(e) for e in target.queue)
        assert equal
        control=dict(case=case['id'],lazy_candidates_equal_to_full=equal,seed_bad_faces=target.seed_bad_faces)
        if args.backend=='cuda':
            gpu=TorchScorer(v);pairs=[target._candidate(e) for e in target.queue]
            quads=np.array([p[2] for p in pairs if p is not None][:128],dtype=np.int64)
            if len(quads):
                a,b=CpuScorer(v).score(quads),gpu.score(quads)
                passed=np.allclose(a[0],b[0],rtol=1e-6,atol=1e-5) and np.allclose(a[1],b[1],rtol=1e-12,atol=1e-12);assert passed
                control.update(gpu_score_passed=bool(passed),angle_max_abs=float(np.max(np.abs(a[0]-b[0]))),area_max_abs=float(np.max(np.abs(a[1]-b[1]))))
        controls.append(control)
        for round_id in range(3):
            if args.backend=='cuda':observations.append(dict(case=case['id'],round=round_id,processes=subprocess.run(['nvidia-smi','--query-compute-apps=pid,process_name','--format=csv,noheader'],capture_output=True,text=True).stdout.strip()))
            for budget_id,budget in enumerate((20,50,100,200)):
                # 相同小角优先方法交错比较全量统计、旧数值检查和安全范围检查，不改变守卫。
                variants=[('targeted_full',True,True),('targeted_reference',True,False),('targeted_fast',True,False)]
                offset=(round_id+budget_id)%3;variants=variants[offset:]+variants[:offset]
                for name,targeted,full_statistics in variants:
                    # 本对照单线程执行；每次调用绑定明确的检查版本，实际源码摘要共同冻结。
                    input_api.check_and_boxes=reference_check if name=='targeted_reference' else range_check
                    state,row=maintain_input(v,f,bits,low,high,budget,args.backend,targeted,full_statistics)
                    assert np.array_equal(state.active,active)
                    if row['before'] is not None:assert row['before']==before
                    # 只追加评价统计，不把它追写成实时路径已计算的全量分布。
                    row['before']=before
                    row.update(case=case['id'],round=round_id,variant=name,after=quality(state.vertices,state.faces),vertices_unchanged=bool(np.array_equal(v,state.vertices)),outside_faces_unchanged=bool(np.array_equal(f[~active],state.faces[~active])),labels_unchanged=bool(np.array_equal(bits,state.bits)),activity_mask_equals_frozen=True)
                    if round_id==0 and name=='targeted_fast':
                        output=out/f'{name}_{case["id"]}_{budget}ms.obj';save_obj(output,state.vertices,state.faces)
                        result=subprocess.run([args.checker,str(output)],capture_output=True,text=True,timeout=120)
                        row.update(output=output.name,sha256=sha(output),embedding=dict(returncode=result.returncode,stdout=result.stdout,stderr=result.stderr))
                    rows.append(row)
            save('running')
        print(case['id'],args.backend,'complete',flush=True)
    save('completed_with_recorded_outcomes')


if __name__=='__main__':main()
