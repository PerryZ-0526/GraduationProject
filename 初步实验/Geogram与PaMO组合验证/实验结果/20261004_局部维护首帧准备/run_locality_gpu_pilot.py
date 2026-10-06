"""预加载CPU模块后逐分支隔离执行局部维护GPU试运行。"""

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
from time import perf_counter
import traceback

import numpy as np
import torch
import trimesh

from locality_gpu import load_extension, run_full, run_locality


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--tool", type=Path, required=True)
    parser.add_argument("--extension", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--methods", nargs="+", default=["full", "global", "spatial", "boolean"])
    parser.add_argument("--rounds", type=int, default=1)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    args.output.mkdir(parents=True)
    extension = load_extension(args.extension)
    if torch.cuda.is_initialized():
        raise RuntimeError("父进程已经初始化CUDA，禁止派生")
    mesh = trimesh.load(args.source, force="mesh", process=False)
    tool = trimesh.load(args.tool, force="mesh", process=False)
    bits = json.loads(args.labels.read_text())["operand_bits"]
    record = {"time_beijing": datetime.now(timezone(timedelta(hours=8))).isoformat(),
              "source_sha256": digest(args.source), "labels_sha256": digest(args.labels),
              "tool_sha256": digest(args.tool), "extension_sha256": digest(args.extension / "build/pamo_locality_cuda.so"),
              "parent_cuda_initialized": False, "source_vertices": len(mesh.vertices), "source_faces": len(mesh.faces),
              "execution": "CPU预加载后每张每方法独立CUDA子进程；不含独立几何审计", "rows": []}
    save(args.output / "01-GPU执行记录.json", record)
    for round_index in range(args.rounds):
        # 每轮旋转顺序，开发试跑后正式配对另冻结随机交错顺序。
        methods = args.methods[round_index % len(args.methods):] + args.methods[:round_index % len(args.methods)]
        for method in methods:
            stem = f"r{round_index}_{method}"
            output = args.output / (stem + ".obj")
            step = args.output / (stem + ".json")
            start = perf_counter()
            pid = os.fork()
            if pid == 0:
                stream = open(args.output / (stem + ".log"), "w", buffering=1)
                os.dup2(stream.fileno(), 1)
                os.dup2(stream.fileno(), 2)
                try:
                    if method == "full":
                        result, details = run_full(mesh)
                    elif method == "stage1off":
                        result, details = run_full(mesh, False)
                    else:
                        mode = "boolean" if method == "boolean_no_transition" else method
                        result, ids, details = run_locality(mesh, bits, tool, mode, extension,
                                                          rings=0 if method == "boolean_no_transition" else 2)
                        np.save(args.output / (stem + "_original_ids.npy"), ids)
                    result.export(output, digits=17)
                    if not np.isfinite(result.vertices).all() or np.any(result.area_faces <= 1e-12):
                        raise RuntimeError("非有限或退化候选，停止该分支扩大")
                    save(step, {"status": "pending_independent_audit", "output_sha256": digest(output), **details})
                    stream.flush()
                    os._exit(0)
                except BaseException as error:
                    traceback.print_exc()
                    save(step, {"status": "execution_failed", "error": str(error)})
                    stream.flush()
                    os._exit(1)
            # 单个子进程最多900秒；超时明确终止，不能继续把输出计为成功。
            status = None
            while perf_counter() - start < 900:
                waited, status = os.waitpid(pid, os.WNOHANG)
                if waited:
                    break
                import time
                time.sleep(0.1)
            else:
                os.kill(pid, 9)
                _, status = os.waitpid(pid, 0)
                save(step, {"status": "execution_failed", "error": "CUDA子进程超时"})
            details = json.loads(step.read_text()) if step.exists() else {"status": "execution_failed", "error": "子进程无记录"}
            row = {"method": method, "round": round_index, "wall_ms": (perf_counter() - start) * 1000,
                   "child_status": status, **details}
            record["rows"].append(row)
            save(args.output / "01-GPU执行记录.json", record)
            print(method, round_index, row["wall_ms"], row["status"], flush=True)
    record["status"] = "completed_with_failures" if any(r["child_status"] for r in record["rows"]) else "pending_independent_audit"
    save(args.output / "01-GPU执行记录.json", record)


if __name__ == "__main__":
    main()
