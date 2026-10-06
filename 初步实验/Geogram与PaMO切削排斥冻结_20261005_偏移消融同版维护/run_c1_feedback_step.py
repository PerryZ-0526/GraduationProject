"""执行一帧冻结C1反馈更新，并记录父网格与两个阶段的摘要。"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
from time import perf_counter


EXPECTED_EXTENSION_SHA256 = "c0836ff8d36fe5c9e2fca8f27e9a341578aa3d716dfb1d0563784710717353ad"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command: list[str], log: Path, timeout: int, env: dict[str, str] | None = None) -> tuple[int, float]:
    started = perf_counter()
    try:
        with log.open("w", encoding="utf-8") as stream:
            result = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT,
                                    timeout=timeout, env=env, check=False)
        return result.returncode, (perf_counter() - started) * 1000
    except subprocess.TimeoutExpired:
        return 124, (perf_counter() - started) * 1000


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--route", required=True)
    parser.add_argument("--event", required=True)
    parser.add_argument("--parent", type=Path, required=True)
    parser.add_argument("--geogram", type=Path, required=True)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--example", type=Path, required=True)
    parser.add_argument("--extension", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    manifest_path = args.inputs / "01-C1试运行清单.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    route = next(item for item in manifest["routes"] if item["id"] == args.route)
    event = next(item for item in route["events"] if item["id"] == args.event)
    if not event["cutting"] or args.event not in route["cutting_prefix_ids"]:
        raise ValueError("仅可执行冻结的有效切削事件")
    tool_info = next(item for item in route["prefix_tools"] if item["event_id"] == args.event)
    tool = args.inputs / tool_info["mesh"]
    if sha256(tool) != tool_info["sha256"] or sha256(args.extension) != EXPECTED_EXTENSION_SHA256:
        raise ValueError("工具或实际加载的CUDA扩展摘要不符")
    if args.event == route["cutting_prefix_ids"][0] and sha256(args.parent) != route["initial_mesh_sha256"]:
        raise ValueError("初始父网格摘要不符")
    args.output.mkdir(parents=True)
    geo = args.output / "geogram.obj"
    pamo = args.output / "pamo.obj"
    geo_rc, geo_ms = run([str(args.geogram), str(args.parent), str(tool), str(geo)],
                         args.output / "geogram.log", 120)
    env = os.environ.copy()
    env["LD_PRELOAD"] = "/usr/lib/x86_64-linux-gnu/libstdc++.so.6"
    env.pop("PYTHONPATH", None)
    pamo_rc, pamo_ms = (None, None)
    if geo_rc == 0 and geo.is_file():
        pamo_rc, pamo_ms = run([str(args.python), str(args.example), "--input", str(geo),
                                "--output", str(pamo), "--ratio", "1.0", "--min-vertex", "0"],
                               args.output / "pamo.log", 900, env)
    result = {
        "schema_version": 1,
        "time_beijing": datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S"),
        "route": args.route, "event": args.event,
        "manifest_sha256": sha256(manifest_path),
        "parent_sha256": sha256(args.parent), "tool_sha256": sha256(tool),
        "geogram_binary_sha256": sha256(args.geogram),
        "example_sha256": sha256(args.example),
        "extension_sha256": sha256(args.extension),
        "geogram": {"returncode": geo_rc, "wall_ms": geo_ms,
                     "sha256": sha256(geo) if geo.is_file() else None},
        "pamo": {"returncode": pamo_rc, "wall_ms": pamo_ms,
                  "sha256": sha256(pamo) if pamo.is_file() else None},
        "audit_status": "pending_independent_audit",
    }
    (args.output / "step.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                                           encoding="utf-8")
    print(json.dumps({"route": args.route, "event": args.event,
                      "geogram_returncode": geo_rc, "pamo_returncode": pamo_rc,
                      "audit_status": result["audit_status"]}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
