"""同机交错比较全邻接、活动邻接和余量策略，将准备计入预算。"""
import argparse
from datetime import datetime,timezone,timedelta
import hashlib
import json
from pathlib import Path
import subprocess
from time import perf_counter
import numpy as np
from benchmark import quality,save_obj
from budget_flip import BudgetFlipState,CpuScorer,TorchScorer
from sparse_budget_flip import SparseBudgetFlipState
from resumable_budget_flip import ResumableBudgetFlipState
from local_guard import LocalGuard


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--backend',choices=('cpu','cuda'),required=True)
    parser.add_argument('--checker',required=True)
    args=parser.parse_args();root=args.root
    manifest=json.loads((root/'02-输入与研究预算冻结.json').read_text(encoding='utf-8'))
    freeze=json.loads((root/'03-执行源码冻结.json').read_text(encoding='utf-8'))
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    # 从实际运行目录核对完整源码，不读取另一个工作目录中的最新版。
    for name,digest in freeze.items():assert sha(root/name)==digest
    out=root/args.backend;out.mkdir(exist_ok=False)
    rows=[];controls=[];sources=[];gpu_observations=[]
    def save(status):
        report=dict(time_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat(),status=status,backend=args.backend,
            source_sha256=freeze,manifest_sha256=sha(root/'02-输入与研究预算冻结.json'),controls=controls,sources=sources,gpu_observations=gpu_observations,rows=rows)
        temporary=out/'record.tmp';temporary.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        temporary.replace(out/'01-完整准备预算与保存对象记录.json')
    for case in manifest['cases']:
        path=root/case['file'].replace('\\','/');assert sha(path)==case['sha256']
        data=np.load(path);v,f,bits,active=[data[k] for k in ('vertices','faces','bits','active')]
        before=quality(v,f)
        source_path=out/f'{case["id"]}_source.obj';save_obj(source_path,v,f)
        result=subprocess.run([args.checker,str(source_path)],capture_output=True,text=True,timeout=120)
        sources.append(dict(case=case['id'],returncode=result.returncode,stdout=result.stdout,stderr=result.stderr))
        factory=lambda v,f:LocalGuard(v,f,manifest['protocol']['local_error_mm'])
        full=BudgetFlipState(v,f,bits,active,'cpu',factory)
        sparse=SparseBudgetFlipState(v,f,bits,active,'cpu',factory)
        equal=list(full.queue)==list(sparse.queue) and all(full._candidate(e)==sparse._candidate(e) for e in full.queue)
        assert equal
        # 充足时间控制只检验相同工作次序，不作为实时性能样本。
        x,y=full.step(5000,max_candidates=128,max_flips=4),sparse.step(5000,max_candidates=128,max_flips=4)
        matched=x['accepted']==y['accepted'] and np.array_equal(full.faces,sparse.faces)
        assert matched
        control=dict(case=case['id'],queue_and_candidates_equal=equal,first_batch_operations_equal=matched,control_adopted=x['accepted'])
        if args.backend=='cuda':
            # 单独记录常驻GPU评分器的预热，不把首次导入藏入已热状态时延。
            warm_start=perf_counter();gpu=TorchScorer(v)
            control['gpu_warmup_ms']=(perf_counter()-warm_start)*1000
            pairs=[sparse._candidate(e) for e in sparse.queue]
            quads=np.array([p[2] for p in pairs if p is not None][:128],dtype=np.int64)
            if len(quads):
                a,b=CpuScorer(v).score(quads),gpu.score(quads)
                passed=np.allclose(a[0],b[0],rtol=1e-6,atol=1e-5) and np.allclose(a[1],b[1],rtol=1e-12,atol=1e-12)
                assert passed
                control.update(gpu_score_passed=bool(passed),angle_max_abs=float(np.max(np.abs(a[0]-b[0]))),area_max_abs=float(np.max(np.abs(a[1]-b[1]))))
        controls.append(control)
        for round_id in range(manifest['protocol']['rounds']):
            if args.backend=='cuda':
                gpu_observations.append(dict(case=case['id'],round=round_id,processes=subprocess.run(['nvidia-smi','--query-compute-apps=pid,process_name','--format=csv,noheader'],capture_output=True,text=True).stdout.strip()))
            for budget_id,budget in enumerate(manifest['protocol']['budgets_ms']):
                # 将余量与中断续跑分开对照，不把两个因素的收益混为一项。
                methods=[('full',BudgetFlipState,0),('sparse',SparseBudgetFlipState,0),('sparse_slack_no_resume',SparseBudgetFlipState,4),('sparse_slack',ResumableBudgetFlipState,4)]
                offset=(round_id+budget_id)%len(methods);methods=methods[offset:]+methods[:offset]
                for name,method,slack in methods:
                    start=perf_counter();state=method(v,f,bits,active,args.backend,factory)
                    # 同一总预算扣掉实际准备时间，再扣余量；准备已超预算时保持原网格。
                    remaining=max(0,budget-(perf_counter()-start)*1000-slack)
                    record=state.maintain(remaining,max_flips=manifest['protocol']['max_flips'])
                    total_ms=(perf_counter()-start)*1000
                    record.update(case=case['id'],round=round_id,variant=name,total_budget_ms=budget,total_elapsed_ms=total_ms,total_budget_overrun=total_ms>budget,
                        reserved_ms=slack,preparation_ms=state.preparation_ms,active_edge_groups=len(state.edges),before=before,after=quality(state.vertices,state.faces),
                        vertices_unchanged=bool(np.array_equal(v,state.vertices)),outside_faces_unchanged=bool(np.array_equal(f[~active],state.faces[~active])),labels_unchanged=bool(np.array_equal(bits,state.bits)))
                    if round_id==0 and name=='sparse_slack':
                        target=out/f'{case["id"]}_{budget}ms.obj';save_obj(target,state.vertices,state.faces)
                        record.update(output=target.name,sha256=sha(target))
                        result=subprocess.run([args.checker,str(target)],capture_output=True,text=True,timeout=120)
                        record['embedding']=dict(returncode=result.returncode,stdout=result.stdout,stderr=result.stderr)
                    rows.append(record)
            save('running')
        print(case['id'],args.backend,'complete',flush=True)
    save('completed_with_recorded_outcomes')


if __name__=='__main__':main()
