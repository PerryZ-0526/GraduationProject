"""真实骨面交付质量对照实验，保存参数、数据、网格及论文用图。"""
import hashlib
import json
import platform
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import trimesh

import real_bone_demo as R
from real_bone_interactive_app import MillingEngine
from mesh_quality import quality, validated_delivery

OUT = Path(__file__).parent / '网格质量交付实验'


def main():
    """固定输入和种子，对不同参数与动态检查点重复验证。"""
    OUT.mkdir(exist_ok=True)
    print('开始真实骨面轨迹回放', flush=True)
    engine = MillingEngine()
    baseline = quality(engine.current_mesh)
    snapshots = {}
    for step in range(1, 139):
        engine.step()
        if step in (60, 110, 138):
            snapshots[step] = engine.current_mesh.copy()
            print('检查点', step, flush=True)
    data = dict(time_beijing=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),
                python=platform.python_version(), platform=platform.platform(),
                input_sha256=hashlib.sha256(Path(R.SCAP_STL).read_bytes()).hexdigest(),
                initial=baseline, trajectory_rows=engine.records, experiments=[])
    runs = [(138, .6, 3), (138, .6, 5), (138, .9, 3), (60, .6, 3),
            (110, .6, 3), (138, .6, 3), (138, .6, 3)]
    for index, (step, edge, iterations) in enumerate(runs):
        name = f'step{step}_edge{edge}_iter{iterations}' + (f'_repeat{index}' if index > 4 else '')
        start = time.perf_counter()
        print('开始重网格', name, flush=True)
        try:
            mesh, evidence = validated_delivery(snapshots[step], R.GC,
                                                edge_mm=edge, iterations=iterations)
            mesh.export(OUT / (name + '.ply'))
            evidence.update(step=step, name=name)
            before_area = engine._risk_counts(snapshots[step])
            after_area = engine._risk_counts(mesh)
            evidence.update(area_before_mm2=before_area, area_after_mm2=after_area)
        except Exception as exc:
            evidence = dict(name=name, step=step, accepted=False, error=str(exc))
        data['experiments'].append(evidence)
        (OUT / 'results.json').write_text(json.dumps(data, ensure_ascii=False, indent=2),
                                         encoding='utf-8')
        print(name, json.dumps(evidence, ensure_ascii=False),
              'wall_s', round(time.perf_counter()-start, 2), flush=True)
    snapshots[138].export(OUT / 'raw_step138.ply')


if __name__ == '__main__':
    main()
