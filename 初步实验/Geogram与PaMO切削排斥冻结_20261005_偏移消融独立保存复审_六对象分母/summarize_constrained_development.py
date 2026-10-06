"""汇总保存帧开发消融，保留失败分母与同输入配对，不扩展为独立样本结论。"""

import argparse
from collections import Counter
import json
from pathlib import Path
import statistics

from run_geometry_study import save, now
from audit_followup_candidate import sha256


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    args = parser.parse_args()
    record = json.loads(args.input.read_text(encoding="utf-8"))
    rows = record["rows"]
    methods = sorted({r["method"] for r in rows})
    summary = {"time_beijing": now(), "input_sha256": sha256(args.input),
        "planned_records": 168, "observed_records": len(rows), "methods": {},
        "scope": "8张已见保存输入、3轮交错；重复输出不视为独立路线；接受仅支持所列抽样检查"}
    baseline = {(r["case"], r["round"]): r for r in rows
                if r["method"] == "full" and r["status"] == "accepted_sampled"}
    for method in methods:
        selected = [r for r in rows if r["method"] == method]
        valid = [r for r in selected if r["status"] == "accepted_sampled"]
        pairs = [(r, baseline[(r["case"], r["round"])]) for r in valid
                 if (r["case"], r["round"]) in baseline]
        item = {"status_counts": dict(Counter(r["status"] for r in selected)),
                "valid_pair_count": len(pairs)}
        if valid:
            item["median_maintenance_ms"] = statistics.median(r["maintenance_ms"] for r in valid)
            item["median_actual_edge_length_mm"] = statistics.median(
                r["actual_edge_length_mm"] for r in valid if "actual_edge_length_mm" in r) if method != "full" else None
            item["median_small_angle_percent"] = {str(a): statistics.median(
                r["quality"][f"angle_below_{a}_deg"]["fraction"] * 100 for r in valid) for a in (10, 5, 1)}
            # 原版不声明固定域契约，记录中的空值不能当作字典或通过。
            item["fixed_contract_passed"] = sum((r.get("fixed_contract") or {}).get("passed", False) for r in valid)
        if pairs:
            item["paired_angle10_percentage_point_change_median"] = statistics.median(
                (r["quality"]["angle_below_10_deg"]["fraction"] - b["quality"]["angle_below_10_deg"]["fraction"]) * 100
                for r, b in pairs)
            item["paired_maintenance_ratio_median"] = statistics.median(
                r["maintenance_ms"] / b["maintenance_ms"] for r, b in pairs)
        summary["methods"][method] = item
    save(args.input.parent / "02-保存帧消融完整分母统计.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
