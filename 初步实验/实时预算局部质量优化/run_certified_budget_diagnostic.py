"""严格原始面集合对拍未通过时，仅执行候选完整GPU反馈诊断并全量复审。"""
import argparse
from datetime import datetime, timezone, timedelta
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root, output = args.root.resolve(), args.output.resolve()
    output.mkdir(exist_ok=False)
    sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
    identity = json.loads((root / 'workers/build_identity.json').read_text())
    assert identity['status'] == 'completed'
    for library in identity['libraries']:
        assert sha(library['path']) == library['sha256']
    strict_path = root / 'static_pair_01/01-已认证双输入候选同源完整对拍.json'
    strict = json.loads(strict_path.read_text())
    assert strict['status'] in ('completed', 'failed')
    record = dict(time_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat(),
                  status='running', diagnostic_only=True, strict_status=strict['status'],
                  strict_sha256=sha(strict_path), build_identity=identity, stages=[],
                  scope='原始三角面集合等同未成立；独立GPU诊断不替代几何等同验证或临床交付')
    record_path = output / '01-完整GPU诊断执行记录.json'

    def save():
        temporary = record_path.with_suffix('.tmp')
        temporary.write_text(json.dumps(record, ensure_ascii=False, indent=2))
        temporary.replace(record_path)

    save()
    environment = dict(os.environ, LD_PRELOAD='/usr/lib/x86_64-linux-gnu/libstdc++.so.6')
    workers = root / 'workers'
    try:
        # 保留原精确父认证和非法源阻断，所有计划事件及超预算仍如实记录。
        stages = [('feedback', [sys.executable, str(workers / 'verified_budget_feedback.py'),
                   '--ct-record', str(root / 'inputs/ct_record.json'), '--output', str(output / 'feedback'),
                   '--fixed-flip-certificate', '--early-quality-return', '--edge-backend', 'cuda',
                   '--certified-operand-pairs']),
                  ('audit', [sys.executable, str(workers / 'audit_verified_budget_feedback.py'),
                             '--root', str(output / 'feedback')])]
        for name, argv in stages:
            with (output / (name + '.log')).open('x') as log:
                result = subprocess.run(argv, cwd=workers, env=environment, stdout=log, stderr=subprocess.STDOUT)
            record['stages'].append(dict(name=name, argv=argv, returncode=result.returncode))
            save()
            assert result.returncode == 0, (name, result.returncode)
        feedback = json.loads((output / 'feedback/01-真实父反馈四预算完整记录.json').read_text())
        assert feedback['certified_operand_pairs'] and feedback['edge_backend'] == 'cuda'
        record['status'] = 'completed'
        save()
    except Exception as error:
        record['status'] = 'failed'
        record['error'] = repr(error)
        save()
        raise


if __name__ == '__main__':
    main()
