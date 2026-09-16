"""远端运行未改动作者Remesh，保存输入摘要、退出码和含初始化的进程耗时。"""
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import time

ROOT = Path('/root/autodl-tmp/graduation_project/build_rxmesh_dynamic_20260908_141858')
INPUT = Path('/root/autodl-tmp/graduation_project/stage1/初步实验/CUDA真实骨面对照/强基线覆盖结果/20260908_132411')


def main():
    now = datetime.now(timezone(timedelta(hours=8)))
    output = ROOT / ('author_' + now.strftime('%Y%m%d_%H%M%S'))
    output.mkdir()
    executable = ROOT / 'build/bin/Remesh'
    if not executable.is_file():
        matches = [p for p in (ROOT / 'build').rglob('Remesh') if p.is_file()]
        if len(matches) != 1:
            raise RuntimeError('未找到唯一Remesh可执行文件')
        executable = matches[0]
    records = []
    for name in ('initial.obj', 'raw_2.obj'):
        source = INPUT / name
        target = output / source.stem
        target.mkdir()
        command = [str(executable), '-i', str(source), '-o', str(target), '-n', '1', '--relative_len', '1']
        start = time.perf_counter()
        # 超时和失败均保留，不能只统计成功运行；此计时不等于GPU核耗时。
        try:
            run = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=90)
            code, log = run.returncode, run.stdout
        except subprocess.TimeoutExpired as exc:
            code, log = 124, exc.stdout or b''
        elapsed = (time.perf_counter() - start) * 1000
        (target / 'run.log').write_bytes(log)
        records.append({'input': str(source), 'sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                        'command': command, 'exit_code': code, 'process_wall_ms': elapsed})
        (output / 'runs.json').write_text(json.dumps({'time_beijing': now.strftime('%Y-%m-%d %H:%M:%S'),
                         'runs': records, 'quality_accepted': None}, ensure_ascii=False, indent=2), encoding='utf-8')
        print(name, code, elapsed, flush=True)
    print(output, flush=True)


if __name__ == '__main__':
    main()
