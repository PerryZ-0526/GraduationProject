"""顺序运行相同真实骨面16步，比较包含CPU审计的核显证书管线。"""
from datetime import datetime, timezone, timedelta
from time import perf_counter
import json
import numpy as np
from experiment import OUT, load_candidate
from integrated import SweepDevice, CheckedGpuPatch
from local_model import LocalPatch
from dynamic import run_sequence


if __name__ == '__main__':
    folder = OUT/datetime.now(timezone(timedelta(hours=8))).strftime('integrated_%Y%m%d_%H%M%S')
    folder.mkdir()
    candidate, chart = load_candidate()
    started = perf_counter()
    device = SweepDevice()
    setup_ms = (perf_counter()-started)*1000
    device.evaluate(np.zeros((1000, 2)), np.zeros(1000), np.array([[0., 0., .25, 0., 3., 1.8]]))
    result = dict(time_bjt=folder.name, device=device.device.name, driver=device.device.driver_version,
                  setup_ms=setup_ms, warmup_calls=1, runs=[])
    for repeat in range(3):
        states = {}
        for method in (['cpu', 'gpu_checked'] if repeat % 2 == 0 else ['gpu_checked', 'cpu']):
            factory = LocalPatch if method == 'cpu' else lambda c, v: CheckedGpuPatch(c, v, device)
            model, records = run_sequence(candidate, chart, 1.8, model_factory=factory)
            assert len(records) == 16 and all(r['accepted'] for r in records)
            states[method] = np.asarray(model.snapshots)
            np.savez_compressed(folder/f'{repeat}_{method}.npz', snapshots=states[method], faces=model.faces, bounds=model.bounds)
            result['runs'].append(dict(repeat=repeat, method=method, records=records))
            (folder/'results.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        np.testing.assert_allclose(states['cpu'], states['gpu_checked'], atol=1e-10, rtol=0.)
        result.setdefault('state_max_deltas_mm', []).append(float(np.abs(states['cpu']-states['gpu_checked']).max()))
        (folder/'results.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(folder, flush=True)
