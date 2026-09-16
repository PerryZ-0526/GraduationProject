"""重复交叉轨迹的长序列稳定性实验，记录每次提交而非只比较最后一帧。"""
import json
from datetime import datetime
from zoneinfo import ZoneInfo
import numpy as np
from experiment import cases, OUT, audit_surface
from patch_model import PatchModel, Rejected


def main():
    model = PatchModel(.25)
    tools = cases()[3][2]
    first = None
    for cycle in range(4):
        for tool in tools:
            try:
                model.update(tool)
            except Rejected:
                break
        else:
            if first is None:
                first = model.vertices.copy()
            else:
                np.testing.assert_array_equal(first, model.vertices)
            print('CYCLE_PASS', cycle+1, len(model.tools), flush=True)
            continue
        break
    data = dict(time_beijing=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),
                requested_steps=64, accepted_steps=len(model.tools),
                repeated_cycle_drift_mm=float(np.max(np.abs(model.vertices-first))) if first is not None else None,
                attempts=model.attempts, final_audit=audit_surface(model))
    OUT.mkdir(exist_ok=True)
    (OUT/'long_sequence.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf8')


if __name__ == '__main__':
    main()
