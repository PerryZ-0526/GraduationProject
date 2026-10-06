"""汇总同GPU加速对照、全量审计与同步分阶段计时。"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import statistics


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stats(values: list[float]) -> dict:
    sorted_values = sorted(values)
    return {"count": len(values), "mean": statistics.mean(values),
            "median": statistics.median(values),
            "p95_nearest_rank": sorted_values[math.ceil(0.95 * len(values)) - 1],
            "max": sorted_values[-1]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    modes = {
        "isolated": ("pamo_speed_isolated_20260929", "05-常驻与独立进程全量审计.json"),
        "resident": ("pamo_speed_resident_20260929", "05-常驻与独立进程全量审计.json"),
        "resident_clear": ("pamo_speed_resident_clear_20260929", "06-fork试运行与清缓存全量审计.json"),
        "preloaded_fork": ("pamo_speed_preloaded_fork_20260929", "07-预加载逐帧fork全量审计.json"),
        "isolated_stage3_3": ("pamo_speed_stage3_3_20260929", "10-安全投影三轮输出审计.json"),
    }
    summaries = {}
    for mode, (directory, audit_name) in modes.items():
        execution_path = args.root / "性能对照" / directory / "report.json"
        audit_path = args.root / audit_name
        execution = json.loads(execution_path.read_text(encoding="utf-8-sig"))
        audit = json.loads(audit_path.read_text(encoding="utf-8-sig"))
        audited = [row for row in audit["rows"] if row["mode"] == mode]
        if len(execution["rows"]) != len(audited):
            raise ValueError(f"执行/审计数量不符: {mode}")
        summaries[mode] = {
            "execution_sha256": sha256(execution_path), "audit_sha256": sha256(audit_path),
            "wall_ms": stats([float(row["wall_ms"]) for row in execution["rows"]]),
            "accepted_sampled": sum(bool(row["accepted_sampled"]) for row in audited),
            "sampled_max_mm": max(row["sampled_max_mm"] for row in audited),
        }
        internal = [row["author_internal_ms"] for row in execution["rows"]
                    if row.get("author_internal_ms") is not None]
        if internal:
            summaries[mode]["author_internal_ms"] = stats(internal)
    original = summaries["isolated"]["wall_ms"]["mean"]
    fork = summaries["preloaded_fork"]["wall_ms"]["mean"]
    logs = list((args.root / "性能对照" / "pamo_stage_sync_20260929").glob("r*.log"))
    timings = {key: [] for key in ("stage1", "stage2", "stage3", "total")}
    patterns = {"stage1": r"SYNC_STAGE1_MS: ([0-9.]+)",
                "stage2": r"SYNC_STAGE2_MS: ([0-9.]+)",
                "stage3": r"SYNC_STAGE3_MS: ([0-9.]+)",
                "total": r"Total time:\s+([0-9.]+)"}
    for log in logs:
        content = log.read_text(encoding="utf-8")
        for key, pattern in patterns.items():
            matched = re.search(pattern, content)
            if matched is None:
                raise ValueError(f"同步计时缺失: {log}/{key}")
            value = float(matched.group(1)) * (1000 if key == "total" else 1)
            timings[key].append(value)
    if len(logs) != 16:
        raise ValueError("同步剖析样本数不符")
    baseline = json.loads((args.root / "性能对照" / "pamo_speed_isolated_20260929" /
                           "report.json").read_text(encoding="utf-8"))
    baseline_first_two = [row for row in baseline["rows"] if row["round"] < 2]
    grouped_path = args.root / "性能对照" / "pamo_speed_grouped_fork_20260929" / "report.json"
    grouped = json.loads(grouped_path.read_text(encoding="utf-8"))
    report = {
        "schema_version": 1,
        "time_beijing": datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S"),
        "scope": "两条已见开发路线8个固定Geogram输入，每种主模式4轮；非真实C1端到端",
        "modes": summaries,
        "isolated_to_preloaded_fork_mean_speedup": original / fork,
        "sync_profile_ms": {key: stats(values) for key, values in timings.items()},
        "stage3_3_vs_original_first_two_rounds": {
            "original_wall_mean_ms": statistics.mean(row["wall_ms"] for row in baseline_first_two),
            "variant_wall_mean_ms": summaries["isolated_stage3_3"]["wall_ms"]["mean"],
            "original_internal_mean_ms": statistics.mean(row["author_internal_ms"]
                                                          for row in baseline_first_two),
            "variant_internal_mean_ms": summaries["isolated_stage3_3"]["author_internal_ms"]["mean"],
        },
        "grouped_fork_status": {"report_sha256": sha256(grouped_path),
                                "completed_groups": len(grouped["groups"]),
                                "failed": any(row.get("error") for row in grouped["rows"])},
    }
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    print(json.dumps({"speedup": report["isolated_to_preloaded_fork_mean_speedup"],
                      "accepted": {key: value["accepted_sampled"] for key, value in summaries.items()}},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
