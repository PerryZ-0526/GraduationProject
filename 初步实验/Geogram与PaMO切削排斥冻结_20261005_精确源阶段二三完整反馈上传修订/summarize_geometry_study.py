"""汇总完整几何体检，保留计划分母、阻断原因及抽样与区间的区别。"""

import argparse
from collections import Counter
import json
from pathlib import Path

from run_geometry_study import now, save


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=Path, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    result = {"time_beijing": now(), "studies": []}
    for folder in args.runs:
        path = folder / "01-连续几何执行与审计.json"
        study = json.loads(path.read_text(encoding="utf-8"))
        item = {"folder": str(folder.resolve()), "status": study["status"], "branches": {}, "routes": []}
        for branch in ("R", "C0", "C1"):
            rows = [r for r in study["rows"] if r["branch"] == branch]
            item["branches"][branch] = {"planned_prefixes": len(rows), "statuses": dict(Counter(r["status"] for r in rows)),
                "pamo_calls": sum("pamo_run" in r for r in rows)}
            for route in sorted({r["route"] for r in rows}):
                selected = [r for r in rows if r["route"] == route]
                valid = [r for r in selected if r["status"] in ("accepted_sampled", "contained_reused", "reference_valid")]
                outputs = [r for r in selected if "preservation" in r]
                entry = {"route": route, "branch": branch, "planned_prefixes": len(selected),
                    "valid_prefixes": len(valid), "full_sampled_sequence": len(valid) == len(selected),
                    "first_stop": next(({"event": r["event"], "status": r["status"],
                        "input_metrics": r.get("input_metrics"), "output_metrics": r.get("output_metrics")}
                        for r in selected if r not in valid), None)}
                # 只对实际生成的候选统计；未执行帧不计成零误差或好质量。
                if outputs:
                    entry["uncut_sampled_max_mm"] = max(r["preservation"]["uncut_sampled_max_mm"] for r in outputs)
                    entry["quality_tail_max_percent"] = {str(t): 100 * max(
                        r["preservation"]["quality_all"][f"angle_below_{t}_deg"]["fraction"] for r in outputs)
                        for t in (10, 5, 1)}
                    entry["sampled_geometry_max_mm"] = max(a["sampled_max_mm"] for r in outputs
                        for key in ("to_cumulative_reference", "to_analytic_discrete_reference")
                        if (a := r.get(key)) is not None) if any(
                            "to_cumulative_reference" in r or "to_analytic_discrete_reference" in r for r in outputs) else None
                item["routes"].append(entry)
        result["studies"].append(item)
    save(args.output, result)
    for item in result["studies"]:
        print(Path(item["folder"]).name, item["branches"], flush=True)


if __name__ == "__main__":
    main()
