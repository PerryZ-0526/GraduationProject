"""独立核对完整反馈分母、真实父哈希与发布版本；不把运行结束当作算法成功。"""

import argparse
import json
from pathlib import Path
from collections import Counter

from audit_followup_candidate import sha256
from run_geometry_study import save, now


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest_path = args.prepared / "01-完整范围冻结清单.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    record_path = args.output / "01-反馈执行与独立审计.json"
    record = json.loads(record_path.read_text(encoding="utf-8"))
    failures = []
    routes = [r for r in manifest["routes"] if r["split"] == record["split"]]
    if record["manifest_sha256"] != sha256(manifest_path):
        failures.append("输入清单摘要不一致")
    route_results = []
    for route in routes:
        rid = route["id"]
        result = {"route": rid, "planned_events": len(route["cutting_prefix_ids"]), "branches": {}}
        for branch in ("full", "candidate"):
            rows = [r for r in record["rows"] if r["route"] == rid and r["branch"] == branch]
            if [r["event"] for r in rows] != route["cutting_prefix_ids"]:
                failures.append(rid + ":" + branch + "计划前缀缺失或重复")
            parent = args.prepared / "inputs" / route["initial_mesh"]
            version = 0
            stopped = False
            for row in rows:
                # 拒绝后的路线不得在缺失父更新的情况下再次发布或复用。
                advancing = row["status"] in ("published_under_sampled_and_vertex_protocol", "contained_reused_parent")
                if stopped and advancing:
                    failures.append(rid + ":" + branch + "拒绝后仍继续更新")
                if not advancing:
                    stopped = True
                if "parent_sha256" in row and row["parent_sha256"] != sha256(parent):
                    failures.append(rid + ":" + branch + ":" + row["event"] + "父摘要不一致")
                if row["status"] == "published_under_sampled_and_vertex_protocol":
                    version += 1
                    candidate = args.output / (rid + "_" + row["event"] + "_" + branch + "_" + row["selected_method"]) / "candidate.obj"
                    if not candidate.exists() or sha256(candidate) != row["output_sha256"]:
                        failures.append(str(candidate) + "候选缺失或摘要不一致")
                    else:
                        parent = candidate
                    if row.get("published_version") != version or not row.get("state_mesh_version一致"):
                        failures.append(rid + ":" + branch + "发布版本不一致")
                    if row["cumulative_geometry"]["probe_max_mm"] > .1:
                        failures.append(rid + ":" + branch + "发布帧超出几何预算")
            final = record.get("route_event_policy", {}).get(rid, {}).get("final_versions", {}).get(branch)
            if final != version:
                failures.append(rid + ":" + branch + "最终版本不一致")
            statuses = Counter(r["status"] for r in rows)
            result["branches"][branch] = {"status_counts": dict(statuses), "published_versions": version,
                "all_events_covered": len(rows) == len(route["cutting_prefix_ids"]) and all(
                    r["status"] in ("published_under_sampled_and_vertex_protocol", "contained_reused_parent") for r in rows),
                "selected_methods": dict(Counter(r["selected_method"] for r in rows if "selected_method" in r))}
        route_results.append(result)
    summary = {"time_beijing": now(), "record_sha256": sha256(record_path), "route_results": route_results,
        "execution_terminal": record["status"] == "completed_with_recorded_failures", "failures": failures,
        "audit_passed": not failures and record["status"] == "completed_with_recorded_failures",
        "scope": "父链、分母、版本和保存数值探针记录；不替代网格重审或连续误差证书"}
    save(args.output / "03-反馈完整分母与父链复核.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if not summary["audit_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
