"""独立全查询对拍轮加三轮正式对照；验证轮性能不混入正式统计。"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
from time import perf_counter
import json
import hashlib
import numpy as np
from interval_device import IntervalDevice, IntervalPatch
from local_model import LocalPatch
from experiment import load_candidate
from dynamic import run_sequence

ROOT=Path(__file__).resolve().parent


def main():
    folder=ROOT/'区间实验结果'/datetime.now(timezone(timedelta(hours=8))).strftime('%Y%m%d_%H%M%S')
    folder.mkdir(parents=True)
    sources=[*ROOT.glob('*.py'),ROOT/'interval_sweep.cu',ROOT.parents[0]/'局部区域重建阶段一/patch_model.py',ROOT.parents[0]/'局部适用域与核显计算/integrated.py']
    result=dict(status='running',runs=[],source_sha256={str(p.relative_to(ROOT.parents[1])):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources})
    def save():
        (folder/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    save()
    try:
        candidate,chart=load_candidate()
        for repeat in range(-1,3):
            states={}
            methods=['interval_512_validate'] if repeat==-1 else ['cpu_512','interval_64','interval_512']
            if repeat>0:
                methods=methods[repeat:]+methods[:repeat]
            for method in methods:
                device=None
                started=perf_counter()
                if method.startswith('interval'):
                    device=IntervalDevice()
                    device.evaluate(np.zeros((100,2)),np.zeros(100),np.array([[0.,0.,.25,0.,3.,1.8]]))
                warmup=(perf_counter()-started)*1000
                def factory(c,v):
                    if method.startswith('interval'):
                        return IntervalPatch(c,v,device,batch=64 if method=='interval_64' else 512,validate=repeat==-1)
                    model=LocalPatch(c,v)
                    model.query_batch_faces=512
                    return model
                started=perf_counter()
                model,records=run_sequence(candidate,chart,1.8,model_factory=factory)
                row=dict(method=method,repeat=repeat,records=records,warmup_ms=warmup,sequence_with_setup_ms=(perf_counter()-started)*1000)
                result['runs'].append(row)
                states[method]=np.asarray(model.snapshots)
                np.savez_compressed(folder/f'{repeat}_{method}.npz',snapshots=states[method],faces=model.faces,bounds=model.bounds)
                save()
                if len(records)!=16 or not all(r['accepted'] for r in records):
                    raise RuntimeError('区间候选未完成全16步验收')
            if repeat>=0:
                for method in ['interval_64','interval_512']:
                    delta=float(np.max(np.abs(states[method]-states['cpu_512'])))
                    result.setdefault('deltas',[]).append(dict(repeat=repeat,method=method,max_delta_mm=delta))
                    if delta>1e-10:
                        raise RuntimeError('状态不一致')
        result['status']='completed'
    except Exception as exc:
        result['status'],result['error']='failed',str(exc)
        raise
    finally:
        save()
        print(folder,flush=True)


if __name__=='__main__':
    main()
