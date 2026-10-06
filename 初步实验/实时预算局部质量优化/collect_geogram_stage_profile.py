"""只汇总能逐次绑定到真实调用标记的作者阶段日志，保留首轮缓冲交错负例。"""
import argparse
from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
import re
import numpy as np


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--log', type=Path, required=True)
    p.add_argument('--first-root', type=Path, required=True)
    p.add_argument('--first-log', type=Path, required=True)
    args = p.parse_args()
    sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
    first_text = args.first_log.read_text()
    first_all = len(re.findall(r'\{"profile_step":', first_text))
    first_aligned = len(re.findall(r'(?m)^\{"profile_step":', first_text))
    assert first_all == 64 and first_aligned < 64
    failure = args.first_root/'02-首轮阶段日志绑定核查失败.json'
    if not failure.exists():
        failure.write_text(json.dumps(dict(time_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat(),
            status='failed_log_binding', markers=first_all, line_aligned_markers=first_aligned,
            log_sha256=sha(args.first_log), scope='实际64次执行完成，缓冲交错不能按调用分配计时；原输入输出保留'),ensure_ascii=False,indent=2))
    d = json.loads((args.root/'01-Geogram内部阶段实际计时与输入绑定.json').read_text())
    text = args.log.read_text()
    markers = list(re.finditer(r'(?m)^\{"profile_step":[^\n]+\}', text))
    assert d['status'] == 'completed' and len(d['rows']) == len(markers) == 64
    assert len(re.findall(r'\{"profile_step":', text)) == len(markers)
    rows = []
    required = ['Prologue', 'Find isects', 'CDT', 'Epilogue', 'Classify', 'Intersect']
    for i, match in enumerate(markers):
        call = json.loads(match.group())
        end = markers[i+1].start() if i+1 < len(markers) else len(text)
        phases = {}
        for label, value in re.findall(r'o-\[([^\]]+)\].*?Elapsed: ([0-9.e+-]+)s', text[match.end():end]):
            phases.setdefault(label.strip(), []).append(float(value)*1000)
        assert all(len(phases.get(k, [])) == 1 for k in required), (call, phases)
        assert call['profile_step'] == d['rows'][i]['step'] and call['repeat'] == d['rows'][i]['repeat']
        rows.append(dict(**call, phases=phases))
    statistics = {}
    for label in required+['AABB build','AABB box-box','AABB tri-tri','I on v','Weiler']:
        values = [x['phases'][label][0] for x in rows if not x['warmup'] and label in x['phases']]
        statistics[label] = dict(samples=len(values), median_ms=float(np.median(values)),
            mean_ms=float(np.mean(values)), p95_ms=float(np.percentile(values,95)))
    report = dict(time_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat(),status='completed',calls=64,measured=48,
        all_main_stages_bound=True,log_sha256=sha(args.log),record_sha256=sha(args.root/'01-Geogram内部阶段实际计时与输入绑定.json'),
        first_binding_failure_sha256=sha(failure),collector_sha256=sha(Path(__file__)),phases=statistics,rows=rows,
        native_boolean_median_ms=float(np.median([x['native_ms'][2] for x in d['rows'] if not x['warmup']])),
        scope='作者日志量化且含输出成本，父子阶段不能加总；仅用于瓶颈定位，64原始输出不发布或反馈')
    target = args.root/'02-Geogram内部阶段日志核对与汇总.json'
    assert not target.exists()
    target.write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps({k:v for k,v in report.items() if k != 'rows'},ensure_ascii=False))


if __name__ == '__main__':
    main()
