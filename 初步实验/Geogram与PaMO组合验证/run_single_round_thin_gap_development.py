"""固定403模块续验薄壁与窄缝六事件，不调整数值参数或改写旧分母。"""

import argparse
from datetime import datetime, timezone, timedelta
import getpass
import hashlib
import json
import os
from pathlib import Path
import runpy
import sys


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def now():
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("snapshot", "prepared", "references", "side-validation", "build-record", "audit-entry", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    manifest = args.snapshot / "01-执行源码冻结清单.json"
    items = json.loads(manifest.read_text("utf8"))
    if len(items) != 403 or any(sha(args.snapshot / item["file"]) != item["sha256"] for item in items):
        raise ValueError("续验必须使用原403模块冻结版本")
    args.output.mkdir(exist_ok=False)
    record = args.output / "01-薄壁窄缝六事件固定续验记录.json"
    report = {"生成时间": now(), "修改时间及修改内容": "首次生成，两路线六事件运行前协议",
              "文档概述": "已见评价负例提升为开发，不称独立评价；几何误差按分布观察",
              "索引目录": ["protocol", "rows"], "status": "running", "rows": [],
              "snapshot_manifest_sha256": sha(manifest), "controller_sha256": sha(Path(__file__)),
              "audit_entry_sha256": sha(args.audit_entry),
              "protocol": {"planned_routes": ["薄壁_新参数1p4375_交叉", "窄缝_新参数1p4375_交叉"],
                           "planned_events": 6, "GPU_worker_budget": 6, "offset": .9, "fallback": False,
                           "no_numerical_tuning": True, "old_outcomes_unchanged": True}}

    def save():
        record.write_text(json.dumps(report, ensure_ascii=False, indent=2), "utf8")

    save()
    project = args.snapshot.resolve().parents[1]
    config = dict(line.split("=", 1) for line in (project / ".env").read_text("utf8").splitlines()
                  if line and not line.startswith("#"))
    original_prompt, original_argv = getpass.getpass, sys.argv
    os.environ["GPU_SSH_HOST"] = "connect.westb.seetacloud.com"
    sys.path.insert(0, str(args.snapshot.resolve()))
    try:
        # 凭据仅供连接，不写入参数或报告；每路线独立目录，失败不重跑。
        getpass.getpass = lambda _: config["CUDA_SSH_PASSWORD"]
        for route in report["protocol"]["planned_routes"]:
            output = args.output / route
            row = {"route": route, "status": "running"}
            report["rows"].append(row)
            save()
            driver = args.snapshot / "run_single_round_distribution_feedback.py"
            sys.argv = [str(driver), "--prepared", str(args.prepared), "--reference-batch", str(args.references / route),
                        "--side-validation", str(args.side_validation), "--build-record", str(args.build_record),
                        "--output", str(output), "--port", "51667", "--route", route, "--offset-factor", "0.9"]
            runpy.run_path(str(driver), run_name="__main__")
            batch = output / "01-统一配置完整父反馈记录.json"
            terminal = json.loads(batch.read_text("utf8"))
            if terminal["status"] != "completed_with_recorded_outcomes" or len(terminal["rows"]) != 3:
                raise ValueError("续验路线未保留完整三事件终态")
            row.update(status="completed", batch_sha256=sha(batch), summary=terminal["summary"])
            save()
            if terminal["summary"]["published"]:
                audit_output = args.output / (route + "_保存独立复审")
                sys.argv = [str(args.audit_entry), "--prepared", str(args.prepared), "--batch", str(output),
                            "--source-batch", str(output), "--side-validation", str(args.side_validation),
                            "--output", str(audit_output), "--kind", "unified"]
                runpy.run_path(str(args.audit_entry), run_name="__main__")
                audit = audit_output / "01-保存候选整面与材料侧独立复审.json"
                result = json.loads(audit.read_text("utf8"))
                if result["status"] != "completed" or result["summary"]["saved_candidates"] != terminal["summary"]["published"]:
                    raise ValueError("实际保存复审分母缺失")
                row.update(audit_sha256=sha(audit), audit_summary=result["summary"])
            save()
        report.update(status="completed_with_recorded_outcomes", finished_beijing=now(),
                      summary={"events": 6, "published": sum(r["summary"]["published"] for r in report["rows"]),
                               "whole_routes": sum(r["summary"]["whole_route_complete"] for r in report["rows"])})
        save()
        print(report["summary"], flush=True)
    finally:
        getpass.getpass, sys.argv = original_prompt, original_argv
        del config


if __name__ == "__main__":
    main()
