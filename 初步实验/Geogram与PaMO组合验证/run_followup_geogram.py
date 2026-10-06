"""在固定Geogram二进制上顺序生成冻结开发路线的各前缀差集。"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from time import perf_counter


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def point_segment_distance(point: list, first: list, second: list) -> float:
    delta = [b - a for a, b in zip(first, second)]
    square = sum(value * value for value in delta)
    t = 0.0 if square == 0 else max(0.0, min(1.0,
        sum((p - a) * d for p, a, d in zip(point, first, delta)) / square))
    return sum((p - a - t * d) ** 2 for p, a, d in zip(point, first, delta)) ** 0.5


def contained(start: list, end: list, previous: list[tuple[list, list]]) -> bool:
    """等半径胶囊的端点都位于旧中心线时，整个新胶囊已被旧胶囊包含。"""
    return any(point_segment_distance(start, a, b) <= 1e-9 and
               point_segment_distance(end, a, b) <= 1e-9 for a, b in previous)


def run_route(route: dict, inputs: Path, output: Path, binary: Path, timeout: int) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    current = inputs / route["initial_mesh"]
    if sha256(current) != route["initial_mesh_sha256"]:
        raise ValueError(f"{route['id']}: 初态哈希不符")
    tools = {item["event_id"]: item for item in route["prefix_tools"]}
    results = []
    retained = []
    last_event = None
    last_timestamp = None
    for event in route["events"]:
        timestamp = event["timestamp_ms"]
        if last_timestamp is not None and timestamp <= last_timestamp:
            results.append({"event_id": event["id"], "status": "late_rejected"})
            continue
        if event["connect_from_previous"] and (last_event is None or not last_event["cutting"]):
            raise ValueError(f"{route['id']}/{event['id']}: 缺少合法连接起点")
        if event["connect_from_previous"] and timestamp - last_timestamp > 200:
            raise ValueError(f"{route['id']}/{event['id']}: 连接间隔超过协议")
        if not event["cutting"]:
            results.append({"event_id": event["id"], "status": "not_cutting"})
            last_event, last_timestamp = event, timestamp
            continue
        start = last_event["position_mm"] if event["connect_from_previous"] else event["position_mm"]
        end = event["position_mm"]
        target = output / f"{event['id']}_geogram.obj"
        if contained(start, end, retained):
            shutil.copy2(current, target)
            results.append({"event_id": event["id"], "status": "contained_reused",
                            "output": target.name, "sha256": sha256(target), "elapsed_ms": 0.0})
        else:
            tool = inputs / tools[event["id"]]["mesh"]
            if sha256(tool) != tools[event["id"]]["sha256"]:
                raise ValueError(f"{route['id']}/{event['id']}: 工具哈希不符")
            command = [str(binary), str(current), str(tool), str(target)]
            started = perf_counter()
            try:
                completed = subprocess.run(command, capture_output=True, text=True,
                                           timeout=timeout, check=False)
                elapsed = (perf_counter() - started) * 1000
                (output / f"{event['id']}_geogram.log").write_text(
                    completed.stdout + completed.stderr, encoding="utf-8")
                if completed.returncode or not target.is_file():
                    results.append({"event_id": event["id"], "status": "geogram_failed",
                                    "returncode": completed.returncode, "elapsed_ms": elapsed})
                    break
            except subprocess.TimeoutExpired as error:
                results.append({"event_id": event["id"], "status": "geogram_timeout",
                                "elapsed_ms": (perf_counter() - started) * 1000})
                break
            retained.append((start, end))
            results.append({"event_id": event["id"], "status": "computed",
                            "output": target.name, "sha256": sha256(target), "elapsed_ms": elapsed})
        current = target
        last_event, last_timestamp = event, timestamp
    successful = [item for item in results if item["status"] in {"computed", "contained_reused"}]
    return {"id": route["id"], "status": "complete" if len(successful) == len(route["cutting_prefix_ids"])
            else "incomplete", "prefixes": results,
            "final": successful[-1]["output"] if successful else None}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--geogram", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=int, default=60)
    parser.add_argument("--limit", type=int, default=6)
    args = parser.parse_args()
    inputs, binary, output = args.inputs.resolve(), args.geogram.resolve(), args.output.resolve()
    if not binary.is_file():
        raise FileNotFoundError(binary)
    if output.exists() and any(output.iterdir()):
        raise ValueError("输出目录已有文件，禁止覆盖")
    manifest = json.loads((inputs / "01-开发输入清单.json").read_text(encoding="utf-8"))
    if len(manifest["routes"]) != 6 or any(item["split"] != "development" for item in manifest["routes"]):
        raise ValueError("开发输入清单不符")
    output.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone(timedelta(hours=8)))
    report = {"schema_version": 1, "time_beijing": now.strftime("%Y-%m-%d %H:%M:%S"),
              "input_manifest_sha256": sha256(inputs / "01-开发输入清单.json"),
              "geogram_binary_sha256": sha256(binary), "routes": []}
    report_path = output / "01-Geogram执行记录.json"
    for route in manifest["routes"][:args.limit]:
        try:
            result = run_route(route, inputs, output / route["id"], binary, args.timeout_seconds)
        except Exception as error:
            result = {"id": route["id"], "status": "input_or_runner_failed", "reason": str(error)}
        report["routes"].append(result)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(route["id"], result["status"], flush=True)


if __name__ == "__main__":
    main()
