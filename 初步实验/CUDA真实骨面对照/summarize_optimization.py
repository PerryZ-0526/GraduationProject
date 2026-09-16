"""从显式指定的原始记录汇总包含式计时与失败，生成可复现图。"""
import argparse
import json
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('folders',nargs='+',type=Path)
    args=parser.parse_args()
    groups={}
    for folder in args.folders:
        result=json.loads((folder/'results.json').read_text(encoding='utf-8'))
        if result['status']!='completed':
            raise RuntimeError('不将未完成批次统计为完整结果')
        for run in result['runs']:
            groups.setdefault(run['method'],[]).extend(run['records'])
    summary={}
    for method,rows in groups.items():
        entry=dict(count=len(rows),accepted=sum(bool(r['accepted']) for r in rows))
        for key in ['total_ms','reference_ms','base_ms','gpu_wall_ms','gpu_kernel_ms','gpu_transfer_ms','gpu_calls','gpu_points','device_buffer_bytes','numeric_interval_width_mm','validation_max_cpu_delta_mm','error_bound_mm','min_angle_deg','min_q']:
            values=np.array([r[key] for r in rows if r.get(key) is not None],dtype=float)
            if len(values):
                entry[key]=dict(mean=float(values.mean()),p95=float(np.percentile(values,95)),p99=float(np.percentile(values,99)),max=float(values.max()),min=float(values.min()))
        entry['over_100ms_rate']=sum(r['total_ms']>100 for r in rows)/len(rows)
        summary[method]=entry
    output=args.folders[-1]
    (output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    names=[name for name in summary if 'validate' not in name]
    fig,ax=plt.subplots(figsize=(11,5.5))
    ax.barh(names,[summary[n]['total_ms']['mean'] for n in names])
    ax.set_xlabel('Update + whole-mesh acceptance (ms), mean of 48 states')
    ax.axvline(100,color='red',linestyle='--',label='100 ms target (not achieved)')
    ax.legend()
    fig.tight_layout()
    fig.savefig(output/'优化计时对照.png',dpi=160)
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
