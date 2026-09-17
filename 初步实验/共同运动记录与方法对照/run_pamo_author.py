"""在NVIDIA环境中批量调用未修改的PaMO作者CLI。"""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from time import perf_counter


PAMO_COMMIT = "a10e34351eb7de71f41eb279e7ab9b2b101cf7a4"


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pamo-root", type=Path, required=True)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--ratio", type=float, default=1.0)
    parser.add_argument("--timeout-seconds", type=int, default=900)
    args = parser.parse_args()

    if args.ratio <= 0:
        raise ValueError("ratio必须为正")
    entrypoint = args.pamo_root.resolve() / "example.py"
    if not entrypoint.is_file():
        raise FileNotFoundError(f"缺少PaMO作者入口: {entrypoint}")
    inputs = sorted(args.input_dir.resolve().glob("*.obj"))
    if not inputs:
        raise FileNotFoundError("输入目录没有OBJ")
    args.output_dir.mkdir(parents=True, exist_ok=False)

    import numpy as np
    import torch
    import trimesh

    now = datetime.now(timezone(timedelta(hours=8)))
    result = {
        "schema_version": 1,
        "time_beijing": now.strftime("%Y-%m-%d %H:%M:%S"),
        "status": "running",
        "method": "PaMO作者三阶段CLI",
        "upstream_commit": PAMO_COMMIT,
        "license": "AGPL-3.0",
        "parameters": {
            "ratio": args.ratio,
            "min_vertices": 0,
            "stage1_enabled": True,
            "stage2_enabled": True,
            "stage3_enabled": True,
            "note": "ratio=1.0令目标面数等于Geogram输入面数，不主动追加低面数压缩",
        },
        "environment": {
            "python": sys.version,
            "numpy": np.__version__,
            "torch": torch.__version__,
            "torch_cuda": torch.version.cuda,
            "cuda_available": torch.cuda.is_available(),
            "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
            "trimesh": trimesh.__version__,
        },
        "runs": [],
    }
    result_path = args.output_dir / "remote_results.json"

    def save():
        result_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    save()
    if not torch.cuda.is_available():
        result["status"] = "failed_no_cuda"
        save()
        return 2

    for source in inputs:
        target = args.output_dir / f"{source.stem}_pamo.obj"
        log = args.output_dir / f"{source.stem}.log"
        command = [
            sys.executable,
            str(entrypoint),
            "--input",
            str(source),
            "--output",
            str(target),
            "--ratio",
            str(args.ratio),
            "--min-vertex",
            "0",
        ]
        started = perf_counter()
        try:
            completed = subprocess.run(
                command,
                cwd=args.pamo_root,
                capture_output=True,
                text=True,
                timeout=args.timeout_seconds,
                check=False,
            )
            return_code = completed.returncode
            content = completed.stdout + completed.stderr
        except subprocess.TimeoutExpired as error:
            return_code = 124
            content = (error.stdout or "") + (error.stderr or "")
        elapsed_ms = (perf_counter() - started) * 1000.0
        log.write_text(content, encoding="utf-8")
        row = {
            "case_id": source.stem,
            "input": source.name,
            "input_sha256": file_hash(source),
            "output": target.name if target.is_file() else None,
            "output_sha256": file_hash(target) if target.is_file() else None,
            "log": log.name,
            "exit_code": return_code,
            "process_wall_ms": elapsed_ms,
        }
        result["runs"].append(row)
        save()
        print(source.stem, return_code, elapsed_ms, flush=True)

    result["status"] = (
        "completed"
        if all(row["exit_code"] == 0 and row["output"] for row in result["runs"])
        else "completed_with_failures"
    )
    save()
    print(result_path, flush=True)
    return 0 if result["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
