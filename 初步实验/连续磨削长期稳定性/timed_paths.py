"""生成同一分段直线路径的不同采样率资产，单位为毫米和秒。"""
from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
import numpy as np


def beijing_now():
    return datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def make_path(rate, duration=100):
    knot_times = np.linspace(0, duration, 11)
    knots = np.array([[0, 0, 2.5], [-1.4, -0.8, 0.7], [1.4, -0.8, 0.7],
                      [1.4, 0.8, 0.1], [-1.4, 0.8, 0.1], [0, -1.2, -0.35],
                      [0, 1.2, -0.35], [0, 1.2, -0.35], [0, 0, 2.5],
                      [-1.4, -0.8, 0.7], [1.4, -0.8, 0.7]], dtype=np.float64)
    times = np.arange(duration * rate + 1, dtype=np.float64) / rate
    centers = np.column_stack([np.interp(times, knot_times, knots[:, i]) for i in range(3)])
    return times, centers, knot_times, knots


def save_assets(folder):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=False)
    rows = []
    for rate in (10, 30, 60):
        times, centers, knot_times, knots = make_path(rate)
        path = folder / f'球钻带时间轨迹_{rate}Hz.npz'
        np.savez_compressed(path, times_s=times, centers_mm=centers,
                            knot_times_s=knot_times, knots_mm=knots)
        rows.append({'file': path.name, 'sha256': digest(path), 'rate_hz': rate,
                     'pose_samples': len(times), 'sweep_events': len(times) - 1})
    manifest = {'created_at_beijing': beijing_now(), 'identity': 'synthetic_development',
                'coordinate_system': '固定右手世界坐标', 'length_unit': 'mm', 'time_unit': 's',
                'duration_s': 100, 'tool': '固定半径球钻', 'radius_mm': 0.4,
                'bodies': ['slab', 'sphere', 'thin_wall', 'gap'],
                'route_features': ['浅磨', '加深', '交叉', '停留', '离开后返回', '重复路线'],
                'assumption': '分段直线中心运动；固定半径；确定性开发轨迹，无临床采集身份',
                'assets': rows}
    (folder / '01-时间轨迹资产清单.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    return manifest
