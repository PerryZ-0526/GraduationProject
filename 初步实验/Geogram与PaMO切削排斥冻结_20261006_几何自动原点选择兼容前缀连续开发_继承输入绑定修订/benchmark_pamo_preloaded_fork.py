"""实验性预加载CPU模块后逐帧派生独立CUDA子进程。"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
from time import perf_counter

import torch
import trimesh
import pamo

from benchmark_pamo_residency import STEMS, run_resident


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path: Path, record: dict) -> None:
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--rounds", type=int, default=4)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    if torch.cuda.is_initialized():
        raise RuntimeError("父进程已初始化CUDA，禁止fork")
    sources = [(name, args.inputs / name / "geogram.obj") for name in STEMS]
    if any(not path.is_file() for _, path in sources):
        raise FileNotFoundError("C1输入未齐全")
    args.output.mkdir(parents=True)
    report = {"schema_version": 1,
              "time_beijing": datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S"),
              "mode": "preloaded_fork", "rounds": args.rounds,
              "parent_cuda_initialized": torch.cuda.is_initialized(),
              "input_sha256": {name: sha256(path) for name, path in sources},
              "rows": []}
    report_path = args.output / "report.json"
    save(report_path, report)
    for round_index in range(args.rounds):
        for name, source in sources:
            stem = f"r{round_index}_{name}"
            output = args.output / f"{stem}.obj"
            log = args.output / f"{stem}.log"
            child_record = args.output / f"{stem}.step.json"
            started = perf_counter()
            pid = os.fork()
            if pid == 0:
                try:
                    result = run_resident(name, source, output, log, False)
                    save(child_record, result)
                    os._exit(0)
                except BaseException as error:
                    save(child_record, {"case": name, "error": str(error)})
                    os._exit(1)
            _, status = os.waitpid(pid, 0)
            wall_ms = (perf_counter() - started) * 1000
            result = (json.loads(child_record.read_text(encoding="utf-8"))
                      if child_record.is_file() else {"case": name, "error": "子进程无结果"})
            row = {"round": round_index, "case": name, "wall_ms": wall_ms,
                   "child_status": status, "child_wall_ms": result.get("wall_ms"),
                   "child_run_ms": result.get("run_ms"),
                   "output_sha256": result.get("output_sha256"),
                   "error": result.get("error")}
            report["rows"].append(row)
            save(report_path, report)
            print(round_index, name, round(wall_ms, 1), row["error"], flush=True)
            if status or not output.is_file():
                raise RuntimeError(f"{stem}失败，停止该分支")


if __name__ == "__main__":
    main()
