"""实验性每四帧复用CUDA子进程，再释放该进程的全部GPU状态。"""

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


def save(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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
    if any(not source.is_file() for _, source in sources):
        raise FileNotFoundError("C1输入未齐全")
    args.output.mkdir(parents=True)
    report = {"schema_version": 1,
              "time_beijing": datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S"),
              "mode": "grouped_fork_4", "rounds": args.rounds, "group_size": 4,
              "parent_cuda_initialized": torch.cuda.is_initialized(),
              "input_sha256": {name: sha256(source) for name, source in sources},
              "groups": [], "rows": []}
    report_path = args.output / "report.json"
    save(report_path, report)
    for round_index in range(args.rounds):
        for group_index in range(2):
            group = sources[group_index * 4:(group_index + 1) * 4]
            started = perf_counter()
            pid = os.fork()
            if pid == 0:
                for name, source in group:
                    stem = f"r{round_index}_{name}"
                    try:
                        result = run_resident(name, source, args.output / f"{stem}.obj",
                                              args.output / f"{stem}.log", False)
                        save(args.output / f"{stem}.step.json", result)
                    except BaseException as error:
                        save(args.output / f"{stem}.step.json",
                             {"case": name, "error": str(error)})
                        os._exit(1)
                os._exit(0)
            _, status = os.waitpid(pid, 0)
            group_wall_ms = (perf_counter() - started) * 1000
            report["groups"].append({"round": round_index, "group": group_index,
                                     "wall_ms": group_wall_ms, "child_status": status})
            for name, _ in group:
                stem = f"r{round_index}_{name}"
                path = args.output / f"{stem}.step.json"
                result = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
                row = {"round": round_index, "group": group_index, "case": name,
                       "wall_ms": result.get("wall_ms"),
                       "run_ms": result.get("run_ms"),
                       "output_sha256": result.get("output_sha256"),
                       "error": result.get("error")}
                report["rows"].append(row)
                print(round_index, group_index, name, row["wall_ms"], row["error"], flush=True)
            save(report_path, report)
            if status or any(row.get("error") or not row.get("output_sha256")
                             for row in report["rows"][-4:]):
                raise RuntimeError(f"r{round_index}/g{group_index}失败，停止该分支")


if __name__ == "__main__":
    main()
