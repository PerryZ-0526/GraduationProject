"""从指定原始运行目录复算统计和科学图，不覆盖原始实验记录。"""
from pathlib import Path
import argparse
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def stats(values):
    a = np.asarray(values, dtype=float)
    return dict(mean=float(a.mean()), p95=float(np.percentile(a, 95)),
                p99=float(np.percentile(a, 99)), min=float(a.min()), max=float(a.max()))


def main(folder):
    data = json.loads((folder/'results.json').read_text(encoding='utf-8'))
    summary = dict(status=data['status'], methods={}, initial=data.get('initial'), state_deltas=data.get('state_deltas'))
    for method in sorted({r['method'] for r in data['runs']}):
        rows = [row for run in data['runs'] if run['method'] == method for row in run['records']]
        item = dict(requests=len(rows), accepted=sum(r.get('accepted') is True for r in rows))
        if method in ('cpu', 'cuda_checked'):
            item['timings_ms'] = {key: stats([r[key] for r in rows if key in r]) for key in
                ['total_ms','local_update_ms','height_ms','certificate_ms','base_ms','reference_ms','gpu_wall_ms','gpu_kernel_ms','gpu_transfer_ms'] if any(key in r for r in rows)}
            item['over_100ms'] = sum(r['total_ms'] > 100 for r in rows)
            item['min_angle_deg'] = min(r.get('min_angle_deg', float('inf')) for r in rows)
            item['max_error_bound_mm'] = max(r.get('error_bound_mm', 0) for r in rows)
            item['max_device_cpu_delta_mm'] = max(r.get('max_gpu_cpu_delta_mm', 0) for r in rows)
        else:
            item['command_successes'] = sum(r['returncode'] == 0 for r in rows)
            valid = [r for r in rows if 'changed' in r]
            if valid:
                item['diagnostic_timings_ms'] = stats([r['candidate_and_diagnostics_ms'] for r in valid])
                item['last_quality'] = valid[-1]
                item['states_with_changed_bad_faces'] = sum(r['changed']['bad_faces'] > 0 for r in valid)
                item['minimum_changed_angle_deg'] = min(r['changed']['min_angle_deg'] for r in valid if r['changed']['min_angle_deg'] is not None)
                item['max_self_intersection_flags'] = max(r['self_intersection_flag_faces'] for r in valid)
        summary['methods'][method] = item
    summary['sampled_errors'] = {method: dict(max_over_states_mm=max(r['sampled_vertical_error_mm']['max'] for r in data['audits'] if r['method']==method),
        final=next(r for r in reversed(data['audits']) if r['method']==method)) for method in sorted({r['method'] for r in data['audits']})}
    (folder/'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    plt.rcParams['font.sans-serif'] = ['Microsoft YaHei','DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.6), constrained_layout=True)
    for method, label, color in [('cpu','CPU逐状态管线','#2878b5'),('cuda_checked','CUDA＋CPU审计','#c94c4c')]:
        runs = [r for r in data['runs'] if r['method']==method]
        if not runs:
            continue
        for i, run in enumerate(runs):
            axes[0].plot([x['step'] for x in run['records']], [x['total_ms'] for x in run['records']], color=color, alpha=.6, label=label if i==0 else None)
    axes[0].axhline(100,color='red',linestyle='--',label='100 ms目标')
    axes[0].set(title='实际更新与整骨检查（不含显示/网络）',xlabel='轨迹步',ylabel='毫秒')
    for method, label in [('local','局部重建'),('geogram_s2','Geogram 工具s2'),('geogram_s3','Geogram 工具s3')]:
        rows = [r for r in data['audits'] if r['method']==method]
        axes[1].plot([r['step'] for r in rows],[r['sampled_vertical_error_mm']['max'] for r in rows],label=label)
    axes[1].axhline(.1,color='red',linestyle='--',label='0.1 mm参考预算')
    axes[1].set(title='公共2048点最大垂直误差（非全域证书）',xlabel='轨迹步',ylabel='毫米')
    for ax in axes:
        ax.grid(alpha=.2)
        ax.legend(fontsize=8)
    fig.savefig(folder/'性能与误差.png',dpi=170)
    plt.close(fig)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('folder', type=Path)
    main(parser.parse_args().folder)
