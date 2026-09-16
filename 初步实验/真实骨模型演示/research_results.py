"""将已有研究证据映射为可视化记录，缺失候选不冒充已发布网格。"""
from pathlib import Path
import json

EXPERIMENTS = Path(__file__).resolve().parents[1]


def series_from_file(path):
    path = Path(path)
    data = json.loads(path.read_text(encoding='utf-8'))
    folder = path.parent
    series = []
    if 'extraction' in data:
        groups = {}
        for row in data['extraction']:
            name = f"解析 / {row['case']} / h={row['spacing_mm']}"
            groups.setdefault(name, []).append(dict(row, mesh=folder/f"{row['case']}_{row['spacing_mm']}_{row['step']}.vtp",
                status='诊断候选；无完整证书', error_bound_mm=None))
        series.extend(groups.items())
    elif 'raw' in data and 'maintenance' in data:
        series.append(('真实整骨 / Geogram未维护诊断', [normalize(row, folder/f"raw_{row['step']}.obj") for row in data['raw']]))
        for edge, rows in data['maintenance'].items():
            series.append((f'真实整骨 / Geogram维护边长{edge}', [normalize(row, folder/f"maint_{edge}_{row['step']}.obj") for row in rows]))
    elif 'state_deltas' in data:
        for run in data['runs']:
            # NPZ仅保存合格局部状态；拒绝行没有候选，不能用上一帧假充失败候选。
            snapshot = 0
            rows = []
            for row in run['records']:
                if row['accepted']:
                    snapshot += 1
                rows.append(dict(row, mesh=folder/f"{run['case']}_{run['method']}.npz",
                    snapshot=snapshot if row['accepted'] else None,
                    status='已验收局部状态（不是整骨显示）' if row['accepted'] else '拒绝；未保存候选网格'))
            series.append((f"真实局部 / {run['case']} / {run['method']}", rows))
    elif data.get('viewer_schema') == 1:
        for name, rows in data['series'].items():
            series.append((name, [dict(row, mesh=folder/row['mesh'] if row.get('mesh') else None) for row in rows]))
    else:
        raise ValueError('尚不支持此报告格式；请选择26/27号或viewer_schema=1结果')
    return [(name, rows) for name, rows in series if rows]


def normalize(row, mesh):
    changed = row.get('changed', {})
    return dict(row, mesh=mesh, min_angle_deg=changed.get('min_angle_deg'), min_q=changed.get('min_q'),
        bad_faces=changed.get('bad_faces'), error_bound_mm=None,
        status=('维护门控通过；仅抽样漂移，非完整证书' if row.get('accepted') else '未合格/诊断候选；禁止临床使用'))


def discover():
    paths = []
    for root in [EXPERIMENTS/'CUDA真实骨面对照/轨迹覆盖结果',
                 EXPERIMENTS/'CUDA真实骨面对照/强基线覆盖结果',
                 EXPERIMENTS/'三维目标几何机制/实验结果']:
        paths.extend(sorted(root.glob('*/results.json')))
    return paths
