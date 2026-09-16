"""相同逐状态门控下五组消融；全部新测量，失败和零收益均保留。"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
from time import perf_counter
import hashlib
import json
import numpy as np
from cuda_device import CudaDevice, CheckedGpuPatch, cp, cpu_sweep
from resident_device import ResidentDevice
from incremental import PrefixSweep, IncrementalCpuPatch
from experiment import load_candidate
from local_model import LocalPatch
from dynamic import run_sequence

ROOT = Path(__file__).resolve().parent


def main():
    folder = ROOT/'增量实验结果'/datetime.now(timezone(timedelta(hours=8))).strftime('%Y%m%d_%H%M%S')
    folder.mkdir(parents=True)
    result = dict(status='running', runs=[], seed=20260908, cupy=cp.__version__,
                  sources={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in ROOT.glob('*.py')})
    def save():
        (folder/'results.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    save()
    try:
        candidate, chart = load_candidate()
        names = ['cpu_full', 'cuda_full_audit', 'cpu_incremental', 'cuda_incremental_audit', 'cuda_resident_incremental_audit']
        for repeat in range(3):
            snapshots = {}
            for name in names[repeat:]+names[:repeat]:
                device = None
                reference = None
                if name.startswith('cuda'):
                    started = perf_counter()
                    device = ResidentDevice() if 'resident' in name else CudaDevice()
                    device.evaluate(np.zeros((100, 2)), np.zeros(100), np.array([[0., 0., 0., 0., 3., 1.8]]))
                    warmup_ms = (perf_counter()-started)*1000
                    reference = PrefixSweep(cpu_sweep) if 'incremental' in name else None
                    factory = lambda c, v: CheckedGpuPatch(c, v, device, reference=reference.evaluate if reference else cpu_sweep)
                else:
                    factory = IncrementalCpuPatch if 'incremental' in name else LocalPatch
                    warmup_ms = 0.
                started = perf_counter()
                model, records = run_sequence(candidate, chart, 1.8, model_factory=factory)
                row = dict(method=name, repeat=repeat, records=records,
                           sequence_with_setup_ms=(perf_counter()-started)*1000, warmup_ms=warmup_ms)
                reference = reference or getattr(model, 'reference_cache', None)
                if reference:
                    row['reference_cache'] = {key: getattr(reference, key) for key in ['bytes', 'hits', 'misses', 'reused_pairs', 'computed_pairs']}
                if isinstance(device, ResidentDevice):
                    row['resident_cache'] = {key: getattr(device, key) for key in ['cache_bytes', 'hits', 'misses', 'reused_pairs', 'computed_pairs']}
                    row['cupy_pool_bytes'] = cp.get_default_memory_pool().total_bytes()
                result['runs'].append(row)
                snapshots[name] = np.asarray(model.snapshots)
                np.savez_compressed(folder/f'{repeat}_{name}.npz', snapshots=snapshots[name], faces=model.faces, bounds=model.bounds)
                save()
                if len(records) != 16 or not all(r['accepted'] for r in records):
                    raise RuntimeError(f'{name}未完成16步验收')
            for name in names[1:]:
                delta = float(np.max(np.abs(snapshots[name]-snapshots['cpu_full'])))
                result.setdefault('state_deltas', []).append(dict(repeat=repeat, method=name, max_delta_mm=delta))
                if delta > 1e-10:
                    raise RuntimeError('与完整CPU序列不一致')
            save()
        result['status'] = 'completed'
    except Exception as exc:
        result['status'], result['error'] = 'failed', str(exc)
        raise
    finally:
        save()
        print(folder, flush=True)


if __name__ == '__main__':
    main()
