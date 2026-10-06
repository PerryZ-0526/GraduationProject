"""对已完整终态且保存复审通过的同版路线汇总误差分布、质量和成本。"""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
# 先初始化共享运动审计模块路径，后续只读取已保存记录。
import run_reference_cut_feedback
from audit_followup_candidate import sha256
from run_geometry_study import now, save


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    scope_bytes = args.scope.read_bytes()
    scope = json.loads(scope_bytes)
    args.output.mkdir(exist_ok=False)
    report = {"生成时间": now(), "修改时间及修改内容": "首次生成，终态与复审完整路线的逐刀趋势",
              "文档概述": "按原八骨32事件报告已覆盖终态子集，运行前缀不混入统计",
              "索引目录": ["rows", "summary"], "scope_sha256": hashlib.sha256(scope_bytes).hexdigest(),
              "original_planned_events": scope["summary"]["planned_events"], "fixed_geometry_acceptance_threshold": None,
              "geometry_quality_decision": "statistics_only_pending_evaluation", "rows": [], "pending_routes": []}
    for entry in scope["rows"]:
        if entry["status"] != "completed_with_recorded_outcomes" or entry["reaudited"] != entry["observed"]:
            report["pending_routes"].append(entry["route"])
            continue
        path = Path(entry["execution_path"])
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != entry["execution_sha256"] or sha256(Path(entry["audit_path"])) != entry["audit_sha256"]:
            raise ValueError("终态或保存复审记录改变")
        batch = json.loads(raw)
        for row in batch["rows"]:
            if row["status"] != "published_geometry_observation":
                report["rows"].append({"route": entry["route"], "event": row["event"], "status": row["status"]})
                continue
            attempt = row["attempt"]
            report["rows"].append({"route": entry["route"], "event": row["event"], "status": row["status"],
                "candidate_sha256": row["output_sha256"], "cumulative_distribution": row["cumulative_distribution"],
                "maintenance_source_distribution": attempt["geometry_distribution_to_maintenance_source"],
                "cutting_surface_distribution": attempt["cutting_surface_distribution"],
                "maximum_cumulative_probe_mm": row["cumulative_geometry"]["probe_max_mm"],
                "maximum_source_probe_mm": attempt["geometry_to_maintenance_source"]["probe_max_mm"],
                "quality": attempt["quality"], "source_quality": attempt["source_quality"],
                "GPU_ms": attempt.get("pamo_run_ms"), "correction_CPU_and_remote_ms": attempt["cut_exclusion"]["correction_cpu_and_remote_audit_ms"]})
    measured = [row for row in report["rows"] if row["status"] == "published_geometry_observation"]
    def range_values(values):
        return {"count": len(values), "minimum": min(values), "median": float(np.median(values)), "maximum": max(values)} if values else None
    report["summary"] = {"terminal_reaudited_events": len(report["rows"]), "observed_reaudited": len(measured),
        "cumulative_area_fraction_within_0_1_mm": range_values([row["cumulative_distribution"]["minimum_bidirectional_area_fraction_within_0_1_mm"] for row in measured]),
        "cut_source_area_fraction_within_0_1_mm": range_values([row["cutting_surface_distribution"]["distribution"]["within_distance_fraction"]["0.1"] for row in measured if row["cutting_surface_distribution"]["status"] == "measured"]),
        "low_angle_fraction_improved_vs_actual_source": sum(row["quality"]["angle_below_10_deg"]["fraction"] < row["source_quality"]["angle_below_10_deg"]["fraction"] for row in measured),
        "maximum_cumulative_probe_mm": range_values([row["maximum_cumulative_probe_mm"] for row in measured]),
        "GPU_ms": range_values([row["GPU_ms"] for row in measured if row["GPU_ms"] is not None]),
        "correction_CPU_and_remote_ms": range_values([row["correction_CPU_and_remote_ms"] for row in measured])}
    # 每档覆盖率与分位数分别报告，双向面积统计取较差方向，不设质量接受比例。
    report["summary"]["cumulative_area_fraction_by_tolerance_mm"] = {
        threshold: range_values([min(row["cumulative_distribution"][direction]["within_distance_fraction"][threshold]
            for direction in ("area_forward", "area_reverse")) for row in measured])
        for threshold in ("0.05", "0.1", "0.15", "0.2")}
    cut_rows = [row["cutting_surface_distribution"]["distribution"] for row in measured
                if row["cutting_surface_distribution"]["status"] == "measured"]
    report["summary"]["cut_source_area_fraction_by_tolerance_mm"] = {
        threshold: range_values([row["within_distance_fraction"][threshold] for row in cut_rows])
        for threshold in ("0.05", "0.1", "0.15", "0.2")}
    report["summary"]["cumulative_area_worst_direction_quantiles_mm"] = {
        quantile: range_values([max(row["cumulative_distribution"][direction]["quantiles_mm"][quantile]
            for direction in ("area_forward", "area_reverse")) for row in measured])
        for quantile in ("0.5", "0.9", "0.95", "0.99")}
    report["summary"]["cut_source_area_quantiles_mm"] = {
        quantile: range_values([row["quantiles_mm"][quantile] for row in cut_rows])
        for quantile in ("0.5", "0.9", "0.95", "0.99")}
    save(args.output / "01-终态观察路线逐刀误差质量与成本.json", report)
    print(report["summary"], flush=True)


if __name__ == "__main__":
    main()
