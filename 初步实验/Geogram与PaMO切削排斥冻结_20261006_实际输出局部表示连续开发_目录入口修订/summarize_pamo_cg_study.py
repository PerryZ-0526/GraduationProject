"""汇总安全投影容量与CG消融的同机计时、输出审计和质量分布。"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import math
from pathlib import Path
import statistics


MODES = (
    ("original", "cg_sync_baseline_20260929", "01-全部输出独立审计.json", 0),
    ("skip_debug_read", "cg_sync_variant_20260929", "01-全部输出独立审计.json", 16),
    ("skip_duplicate_zero", "cg_zero_variant_20260929", "04-重复清零变体独立审计.json", 0),
    ("contact_capacity_1m", "contact_capacity_1m_outputs_20260929", "02-接触容量104万输出独立审计.json", 0),
    ("contact_capacity_64k", "contact_capacity_64k_outputs_20260929", "03-接触容量65536输出独立审计.json", 0),
    ("original_post", "cg_sync_baseline_post_20260929", "06-末尾原版复跑独立审计.json", 0),
)


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    result = {
        "time_beijing": datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S"),
        "interpretation": "两条已见解析开发路线，8帧各重复2次；同卡顺序运行，不是16条独立路线",
        "modes": {},
    }
    for label, directory, audit_file, offset in MODES:
        execution = read(args.directory / directory / "report.json")
        rows = execution["rows"]
        audited = read(args.directory / audit_file)["rows"][offset:offset + len(rows)]
        if len(rows) != 16 or len(audited) != 16:
            raise ValueError(f"结果数量不符: {label}")
        if any(row["output_sha256"] != audit["candidate_sha256"] for row, audit in zip(rows, audited)):
            raise ValueError(f"审计与性能运行不匹配: {label}")
        times = sorted(row["wall_ms"] for row in rows)
        result["modes"][label] = {
            "runs": len(rows),
            "accepted_sampled": sum(audit["accepted_sampled"] for audit in audited),
            "mean_ms": statistics.mean(times),
            "median_ms": statistics.median(times),
            "p95_nearest_rank_ms": times[math.ceil(.95 * len(times)) - 1],
            "max_ms": max(times),
            "worst_sampled_max_mm": max(audit["sampled_max_mm"] for audit in audited),
            "worst_angle_below_10_fraction": max(audit["quality"]["angle_below_10_deg"]["fraction"] for audit in audited),
            "worst_angle_below_5_fraction": max(audit["quality"]["angle_below_5_deg"]["fraction"] for audit in audited),
            "worst_angle_below_1_fraction": max(audit["quality"]["angle_below_1_deg"]["fraction"] for audit in audited),
            "per_case_mean_ms": {
                name: statistics.mean(row["wall_ms"] for row in rows if row["case"] == name)
                for name in sorted({row["case"] for row in rows})
            },
        }
    original = result["modes"]["original"]["mean_ms"]
    for label, mode in result["modes"].items():
        mode["mean_speedup_vs_original"] = original / mode["mean_ms"]
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({label: {key: val for key, val in mode.items() if key in (
        "accepted_sampled", "mean_ms", "p95_nearest_rank_ms", "mean_speedup_vs_original")}
        for label, mode in result["modes"].items()}, ensure_ascii=False))


if __name__ == "__main__":
    main()
