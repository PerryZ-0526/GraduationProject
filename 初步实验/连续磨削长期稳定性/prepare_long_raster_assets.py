"""准备2000秒工程磨削路径，采样跨越的所有转折均位于公共整数秒。"""
import argparse
from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
import numpy as np


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    seed = 2026100610
    rng = np.random.default_rng(seed)
    rows = []
    for body, top, last_depth in [('thin_wall', .18, .12), ('gap', .8, .36)]:
        q = rng.normal(size=4)
        w, x, y, z = q / np.linalg.norm(q)
        rotation = np.array([[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
                             [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
                             [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]])
        shift = rng.uniform(-.08, .08, size=3)
        jitter = rng.uniform(-.02, .02, size=2)
        local, knot_times = [[0., 0., 2.5]], [0]
        for pass_id, depth in enumerate(np.linspace(.06, last_depth, 10)):
            height = top + .4 - depth
            targets = [[-1.65 + jitter[0], -1.3 + jitter[1], height]]
            for row_id, yy in enumerate(np.linspace(-1.3, 1.3, 6)):
                targets.append([(-1.65 if row_id % 2 else 1.65) + jitter[0], yy + jitter[1], height])
                if row_id < 5:
                    targets.append([targets[-1][0], np.linspace(-1.3, 1.3, 6)[row_id+1] + jitter[1], height])
            if len(targets) != 12:
                raise ValueError('每层应有12段实际路径')
            # 前11段各16秒、末段24秒；整数秒转折由10/30/60Hz采样共同覆盖，不跨角取捷径。
            for index, target in enumerate(targets):
                local.append(target)
                knot_times.append(pass_id * 200 + (index + 1) * 16 if index < 11 else (pass_id + 1) * 200)
        local = np.asarray(local)
        knot_times = np.asarray(knot_times, dtype=float)
        knots = local @ rotation.T + shift
        if len(knots) != 121 or knot_times[-1] != 2000 or np.any(np.diff(knot_times) <= 0):
            raise ValueError('实际2000秒连续路径不完整')
        if np.any(np.minimum(knots[:-1], knots[1:]) - .4 - .12 < -3.6) or np.any(np.maximum(knots[:-1], knots[1:]) + .4 + .12 > 3.6):
            raise ValueError('实际扫掠或提取窄带越界')
        for rate in (10, 30, 60):
            times = np.arange(2000 * rate + 1, dtype=float) / rate
            centers = np.column_stack([np.interp(times, knot_times, knots[:, axis]) for axis in range(3)])
            knot_indices = (knot_times * rate).astype(int)
            if not np.array_equal(times[knot_indices], knot_times) or not np.array_equal(centers[knot_indices], knots):
                raise ValueError('转折未由实际采样逐位覆盖')
            file = args.output / f'{body}_{rate}Hz_2000秒.npz'
            np.savez_compressed(file, times_s=times, centers_mm=centers, knot_times_s=knot_times, knots_mm=knots,
                                local_knots_mm=local, rotation=rotation, shift_mm=shift)
            rows.append({'body': body, 'rate_hz': rate, 'file': str(file), 'sha256': digest(file),
                         'planned_received_poses': len(times), 'planned_material_events': len(times)-1,
                         'duration_s': 2000, 'turning_points_exactly_sampled': True,
                         'load_prefixes_events': {'100秒':100*rate, '500秒':500*rate, '2000秒':2000*rate},
                         'motion_lengths_mm': float(np.linalg.norm(np.diff(knots,axis=0),axis=1).sum()),
                         'nominal_max_depth_mm': last_depth, 'nominal_uncut_base_thickness_mm': 2*top-last_depth})
    record = {'generated_at_beijing': datetime.now(timezone(timedelta(hours=8))).isoformat(), 'seed': seed,
              'generator_sha256': digest(Path(__file__)), 'radius_mm': .4, 'planned_spacing_mm': .06,
              'assets': rows, 'scope': '合成长时浅磨/加深/交叉/重复开发负载；尚未运行材料或表面维护；不代替薄壁穿透、真实骨面或完整GPU四分支',
              'positive_removal_events': None, 'positive_removal_scope': '必须实测，不能用计划事件数代替有效切削数量'}
    (args.output / '01-完整2000秒三采样率开发资产清单.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'assets':len(rows),'planned_material_events_sum':sum(x['planned_material_events'] for x in rows),'actual_maintenance_outputs':0}))


if __name__ == '__main__':
    main()
