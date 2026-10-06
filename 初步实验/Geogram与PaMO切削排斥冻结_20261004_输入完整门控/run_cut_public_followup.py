"""顺序执行其余六骨完整开发并独立复审，保留全部失败与阻断分母。"""

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from zoneinfo import ZoneInfo


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--reference-batch", type=Path, required=True)
    parser.add_argument("--side-validation", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    args.output.mkdir(exist_ok=False)
    manifest = json.loads((args.prepared / "01-完整范围冻结清单.json").read_text("utf8"))
    routes = [r for r in manifest["routes"] if not r["id"].startswith(("BP3D_FJ3384_", "BP3D_FJ3279_"))]
    if len(routes) != 6:
        raise ValueError("本次范围必须是明确其余六骨")
    now = lambda: datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()
    report = {"生成时间": now(), "修改时间及修改内容": "首次生成，六骨24事件执行前冻结",
              "文档概述": "3384与3279由先行批次单列，本批不是独立评价",
              "索引目录": ["routes", "rows", "summary"], "status": "running",
              "snapshot_manifest_sha256": hashlib.sha256((args.snapshot / "01-执行源码冻结清单.json").read_bytes()).hexdigest(),
              "routes": [r["id"] for r in routes], "maximum_new_GPU_calls": 24, "rows": []}
    record = args.output / "01-六骨完整范围与执行记录.json"
    def save():
        record.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf8")
    save()
    common = ["--prepared", str(args.prepared), "--side-validation", str(args.side_validation)]
    for route in routes:
        rid = route["id"]
        batch = args.output / rid
        entry = {"route": rid, "planned_events": len(route["cutting_prefix_ids"]), "status": "running"}
        report["rows"].append(entry)
        save()
        print("route_started", rid, flush=True)
        run = subprocess.run([sys.executable, "-X", "utf8", str(args.snapshot / "run_cut_unified_feedback.py"),
            *common, "--reference-batch", str(args.reference_batch), "--output", str(batch), "--route", rid, "--port", str(args.port)])
        entry["execution_returncode"] = run.returncode
        if not run.returncode:
            result = json.loads((batch / "01-统一配置完整父反馈记录.json").read_text("utf8"))
            entry.update(status=result["status"], summary=result["summary"])
            save()
            audit = subprocess.run([sys.executable, "-X", "utf8", str(args.snapshot / "audit_reference_cut_outputs.py"),
                *common, "--batch", str(batch), "--source-batch", str(batch), "--output", str(args.output / (rid + "_保存复审")), "--kind", "unified"])
            entry["reaudit_returncode"] = audit.returncode
            if not audit.returncode:
                entry["reaudit_summary"] = json.loads((args.output / (rid + "_保存复审") / "01-保存候选整面与材料侧独立复审.json").read_text("utf8"))["summary"]
        else:
            # 子进程异常不冒充正常拒绝或完整结果；保持已保存证据，另骨仍能独立推进。
            entry["status"] = "execution_exception_requires_review"
        save()
    report.update(status="completed_with_recorded_outcomes", finished_beijing=now(), summary={
        "routes": len(routes), "planned_events": sum(r["planned_events"] for r in report["rows"]),
        "published": sum(r.get("summary", {}).get("published", 0) for r in report["rows"]),
        "complete_routes": sum(r.get("summary", {}).get("whole_route_complete", False) for r in report["rows"]),
        "execution_exceptions": sum(r["status"] == "execution_exception_requires_review" for r in report["rows"])})
    save()
    print(report["summary"], flush=True)


if __name__ == "__main__":
    main()
