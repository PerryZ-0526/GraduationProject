"""真实计划适用性及变轨迹CPU/CUDA逐状态对照；拒绝后不继续发布。"""
from pathlib import Path
from datetime import datetime,timezone,timedelta
from collections import Counter
import json
import hashlib
import numpy as np
from interval_device import IntervalDevice,IntervalPatch
from experiment import load_candidate
from local_model import LocalPatch
from real_patch import Sweep
from dynamic import run_sequence
from coverage_inputs import original_plan,classify,variant_trajectories

ROOT=Path(__file__).resolve().parent


def main():
    folder=ROOT/'轨迹覆盖结果'/datetime.now(timezone(timedelta(hours=8))).strftime('%Y%m%d_%H%M%S')
    folder.mkdir(parents=True)
    candidate,chart=load_candidate()
    plan=original_plan()
    result=dict(status='running',original_plan=plan,phase_counts=dict(Counter(t['phase'] for t in plan)),runs=[])
    result['plan_sha256']=hashlib.sha256(json.dumps(plan,sort_keys=True).encode()).hexdigest()
    result['original_preflight']=[dict(step=t['step'],phase=t['phase'],reasons=classify(t,candidate,chart)) for t in plan]
    def save():
        (folder/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    save()
    try:
        # 只执行首个不支持段之前的连续前缀；其余段的独立诊断不是成功状态。
        first=next((r for r in result['original_preflight'] if r['reasons']),None)
        allowed=plan[:first['step']-1] if first else plan
        device=IntervalDevice()
        tools=[Sweep(tuple(t['start'][:2]),tuple(t['end'][:2]),t['radius'],t['start'][2]) for t in allowed]
        model,rows=run_sequence(candidate,chart,model_factory=lambda c,v:IntervalPatch(c,v,device,batch=512),trajectory=tools)
        accepted=sum(bool(r['accepted']) for r in rows)
        result['original_sequence']=dict(accepted_prefix=accepted,total=138,records=rows,
            first_preflight_rejection=first,not_executed_after_rejection=138-accepted-(1 if first else 0))
        save()
        for case,trajectory in variant_trajectories().items():
            snapshots={}
            for method in ['cpu','cuda']:
                def factory(c,v):
                    if method=='cuda':
                        return IntervalPatch(c,v,device,batch=512)
                    model=LocalPatch(c,v)
                    model.query_batch_faces=512
                    return model
                model,rows=run_sequence(candidate,chart,model_factory=factory,trajectory=trajectory)
                entry=dict(case=case,method=method,requested=len(trajectory),accepted=sum(bool(r['accepted']) for r in rows),
                    not_executed=len(trajectory)-len(rows),records=rows,trajectory=[t.__dict__ for t in trajectory])
                result['runs'].append(entry)
                snapshots[method]=np.asarray(model.snapshots)
                np.savez_compressed(folder/f'{case}_{method}.npz',snapshots=snapshots[method],faces=model.faces,bounds=model.bounds)
                save()
            same=snapshots['cpu'].shape==snapshots['cuda'].shape
            delta=float(np.max(np.abs(snapshots['cpu']-snapshots['cuda']))) if same else None
            result.setdefault('state_deltas',[]).append(dict(case=case,same_shape=same,max_delta_mm=delta))
            if not same or delta>1e-10:
                raise RuntimeError('变轨迹CPU/CUDA发布状态不一致')
            save()
        result['status']='completed'
    except Exception as exc:
        result['status'],result['error']='failed',str(exc)
        raise
    finally:
        save()
        print(folder,flush=True)


if __name__=='__main__':
    main()
