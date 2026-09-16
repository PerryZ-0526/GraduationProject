"""汇总全计划诊断、连续前缀和未执行段；不混合抽样门控与正式证书。"""
from pathlib import Path
from collections import Counter
import argparse
import json
import numpy as np
import matplotlib.pyplot as plt


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('cuda',type=Path)
    parser.add_argument('baseline',type=Path)
    args=parser.parse_args()
    cuda=json.loads((args.cuda/'results.json').read_text(encoding='utf-8'))
    baseline=json.loads((args.baseline/'results.json').read_text(encoding='utf-8'))
    if cuda['plan_sha256']!=baseline['plan_sha256']:
        raise RuntimeError('原计划输入摘要不一致，禁止汇总为共同任务')
    result=dict(cuda_status=cuda['status'],baseline_status=baseline['status'],original=cuda['original_sequence'],
                phases=cuda['phase_counts'],reason_counts=dict(Counter(reason for r in cuda['original_preflight'] for reason in r['reasons'])),variants=[])
    for run in cuda['runs']:
        times=np.array([r['total_ms'] for r in run['records']])
        failure=next((r for r in run['records'] if not r['accepted']),None)
        result['variants'].append(dict(case=run['case'],method=run['method'],accepted=run['accepted'],requested=run['requested'],
            not_executed=run['not_executed'],failure=failure,mean_ms=float(times.mean()),max_ms=float(times.max())))
    result['baseline_raw']=dict(executed=len(baseline['raw']),unexecuted=baseline['raw_unexecuted'],
        quality_gate_count=sum(r['quality_gate'] for r in baseline['raw']),
        first_bad=next((r['step'] for r in baseline['raw'] if not r['quality_gate']),None),
        last=baseline['raw'][-1] if baseline['raw'] else None,error=baseline.get('error'))
    result['maintenance']={edge:dict(attempted=len(rows),accepted=sum(r['accepted'] for r in rows),last=rows[-1] if rows else None)
                           for edge,rows in baseline['maintenance'].items()}
    # 同物理路径不同分段的末态另核对，不能用完成步数直接比较覆盖范围。
    control=np.load(args.cuda/'control_cuda.npz')['snapshots'][-1]
    result['resampled_final_delta_mm']={name:float(np.max(np.abs(np.load(args.cuda/f'{name}_cuda.npz')['snapshots'][-1]-control)))
                                        for name in ['fine_32','coarse_8']}
    (args.cuda/'summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    rows=[r for r in result['variants'] if r['method']=='cuda']
    fig,ax=plt.subplots(figsize=(9,4.5))
    ax.barh([r['case'] for r in rows],[r['requested'] for r in rows],color='#cccccc',label='Requested')
    ax.barh([r['case'] for r in rows],[r['accepted'] for r in rows],color='#268b90',label='Accepted prefix')
    ax.set_xlabel('Trajectory segments (different step lengths are not interchangeable)')
    ax.legend()
    fig.tight_layout()
    fig.savefig(args.cuda/'真实骨面轨迹覆盖.png',dpi=160)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
