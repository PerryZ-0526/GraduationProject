"""原八骨32事件统一误差分布，不设新的固定达标比例或改变历史发布状态。"""

import argparse
import json
from pathlib import Path

import numpy as np
import trimesh
import run_reference_cut_feedback
from audit_followup_candidate import sha256
from geometry_error_distribution import geometry_error_distribution
from run_geometry_study import now, save


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    scope = json.loads(args.scope.read_text("utf8"))
    if scope["status"] != "completed" or len(scope["rows"]) != 8:
        raise ValueError("要求原八骨完整终态范围")
    args.output.mkdir(exist_ok=False)
    report = {"生成时间": now(), "修改时间及修改内容": "首次生成，按用户要求只统计再定比例",
              "文档概述": "八骨原32事件，已发布和实际拒绝输出均报告，阻断仍为未运行",
              "索引目录": ["protocol", "rows", "summary"], "status": "running",
              "scope_sha256": sha256(args.scope), "new_GPU_calls": 0,
              "protocol": {"area_samples_per_direction": 8192, "seeds": [20260922, 20260923],
                           "distance_thresholds_mm": [.05, .1, .15, .2], "fixed_coverage_acceptance_threshold": None,
                           "vertices_reported_separately": True, "historical_publication_state_unchanged": True}, "rows": []}
    record = args.output / "01-八骨完整事件误差分布重评.json"
    save(record, report)
    for entry in scope["rows"]:
        execution_path = Path(entry["execution_path"])
        if sha256(execution_path) != entry["execution_sha256"]:
            raise ValueError("已核对执行记录变化")
        batch = json.loads(execution_path.read_text("utf8"))
        rid, folder = entry["route"], execution_path.parent
        for event in batch["rows"]:
            row = {"route": rid, "event": event["event"], "historical_status": event["status"]}
            report["rows"].append(row)
            if "attempt" not in event:
                row["distribution_status"] = "not_executed_no_output"
                continue
            attempt = event["attempt"]
            prefix = rid + "_" + event["event"]
            candidate_path = folder / (prefix + "_candidate_boolean") / "candidate.obj"
            source_path = folder / (prefix + "_candidate_input") / "clean_source.obj"
            reference_path = folder / (prefix + "_reference") / "validated_reference.obj"
            if not reference_path.exists():
                reference_path = reference_path.with_name("reference.obj")
            paths = {"candidate": candidate_path, "maintenance_source": source_path, "cumulative_reference": reference_path}
            expected = {"candidate": attempt["output_sha256"], "maintenance_source": attempt["inputs_sha256"]["source.obj"],
                        "cumulative_reference": attempt["cut_exclusion"]["cumulative_reference_sha256"]}
            if any(sha256(path) != expected[name] for name, path in paths.items()):
                raise ValueError("实际候选或参照摘要变化")
            row["bindings"] = {name: {"path": str(path.resolve()), "sha256": expected[name]} for name, path in paths.items()}
            row["historical_exclusion_accepted"] = attempt["cut_exclusion"]["accepted"]
            row["historical_embedding"] = attempt["exact_embedding"].get("embedded_closed")
            candidate = trimesh.load(candidate_path, force="mesh", process=False)
            row["geometry"] = {name: geometry_error_distribution(candidate, trimesh.load(path, force="mesh", process=(name == "cumulative_reference")))
                               for name, path in paths.items() if name != "candidate"}
            row["distribution_status"] = "measured"
            save(record, report)
            print(rid, event["event"], event["status"], {name: round(value["minimum_bidirectional_area_fraction_within_0_1_mm"], 6) for name, value in row["geometry"].items()}, flush=True)
    measured = [row for row in report["rows"] if row["distribution_status"] == "measured"]
    summary = {"planned_events": len(report["rows"]), "measured_outputs": len(measured),
               "blocked_unmeasured": len(report["rows"]) - len(measured), "historically_published": sum(row["historical_status"] == "published" for row in report["rows"])}
    for state in ("published", "candidate_rejected"):
        group = [row for row in measured if row["historical_status"] == state]
        summary[state] = {}
        for reference in ("maintenance_source", "cumulative_reference"):
            values = [row["geometry"][reference]["minimum_bidirectional_area_fraction_within_0_1_mm"] for row in group]
            if values:
                summary[state][reference] = {"count": len(values), "minimum": min(values), "median": float(np.median(values)), "maximum": max(values)}
    report.update(status="completed", finished_beijing=now(), summary=summary)
    save(record, report)
    print(summary, flush=True)


if __name__ == "__main__":
    main()
