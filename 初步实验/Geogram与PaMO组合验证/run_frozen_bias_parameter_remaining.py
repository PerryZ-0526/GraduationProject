"""按既定七家族两档协议续验，不重复已结束的板体，不在新输入上调参。"""

import argparse
from datetime import datetime, timezone, timedelta
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).parents[2]
DATA = Path("D:/GraduationProject_切削排斥证据")
METHOD = ROOT / "初步实验/Geogram与PaMO切削排斥冻结_20261005_两档新参数七家族评价"
PREPARED = DATA / "可复用磨削测试集/两档切削排斥新参数七家族_v28"
REFERENCES = DATA / "20261005_两档新参数七家族独立参照生成"
SIDE = ROOT / "初步实验/Geogram与PaMO组合验证/实验结果/20261004_切削排斥精确材料侧分类开发"
BUILD = ROOT / "初步实验/Geogram与PaMO组合验证/实验结果/20261004_简化邻接顺序隔离构建/01-简化邻接顺序隔离构建.json"
AUDITOR = ROOT / "初步实验/Geogram与PaMO切削排斥冻结_20261005_分布观察控制与复审/audit_distribution_observation_outputs.py"


def read(path):
    return json.loads(path.read_text("utf-8-sig"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def now():
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    mp = PREPARED / "01-完整范围冻结清单.json"
    manifest = read(mp)
    for item in read(METHOD / "01-执行源码冻结清单.json"):
        if sha(METHOD / item["file"]) != item["sha256"]:
            raise ValueError("执行前冻结方法摘要不符")
    args.output.mkdir(exist_ok=False)
    rows = [{"route": r["id"], "offset_factor": factor, "planned_events": len(r["cutting_prefix_ids"]),
             "status": "not_started"} for r in manifest["routes"] for factor in (0.0, 0.9)]
    report = {"生成时间": now(), "修改时间及修改内容": "首次生成，固定14条分支及42事件，不重复板体",
              "文档概述": "顺序执行冻结方法、每条终态后保存独立复审；全部拒绝及阻断保留",
              "索引目录": ["evidence", "rows", "summary"], "status": "running", "rows": rows,
              "evidence": {"manifest_sha256": sha(mp), "method_manifest_sha256": sha(METHOD / "01-执行源码冻结清单.json"),
                           "controller_sha256": sha(Path(__file__)), "auditor_sha256": sha(AUDITOR)}}
    record = args.output / "01-七家族两档完整分母执行与保存复审.json"

    def save():
        # 同目录临时文件原子替换，保留上一次完整快照。
        temporary = record.with_suffix(".tmp")
        temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2), "utf8")
        temporary.replace(record)

    environment = dict(os.environ, GPU_SSH_HOST="connect.westb.seetacloud.com")

    def run(arguments):
        result = subprocess.run([sys.executable, "-X", "utf8", *map(str, arguments)], cwd=ROOT, env=environment)
        if result.returncode:
            raise RuntimeError(f"独立子进程退出{result.returncode}，保留原目录和未执行分母，不自动重跑")

    save()
    for index, route in enumerate(manifest["routes"]):
        rid = route["id"]
        for factor in (0.0, 0.9):
            row = next(r for r in rows if r["route"] == rid and r["offset_factor"] == factor)
            branch = args.output / rid / f"偏移{factor}"
            audit = args.output / rid / f"偏移{factor}_保存复审"
            if index == 0:
                # 首路线两批已终态，只继承真实记录；零偏移已有保存复审不重复。
                branch = DATA / ("20261005_新参数板体三刀零偏移冻结评价" if factor == 0.0 else
                                 "20261005_新参数板体三刀原偏移冻结评价")
                if factor == 0.0:
                    audit = DATA / "20261005_新参数板体零偏移已发布保存独立复审"
            branch.parent.mkdir(parents=True, exist_ok=True)
            # 继承板体执行目录与新保存复审目录可能位于不同父目录。
            audit.parent.mkdir(parents=True, exist_ok=True)
            row.update(status="executing", batch_path=str(branch), audit_path=str(audit), execution_inherited=index == 0)
            save()
            if index != 0:
                run([METHOD / "run_bias_distribution_feedback.py", "--prepared", PREPARED, "--reference-batch", REFERENCES / rid,
                     "--side-validation", SIDE, "--output", branch, "--port", args.port, "--route", rid,
                     "--build-record", BUILD, "--offset-factor", factor])
            bp = branch / "01-统一配置完整父反馈记录.json"
            batch = read(bp)
            if (batch["status"] != "completed_with_recorded_outcomes" or batch["manifest_sha256"] != sha(mp) or
                    batch["protocol"]["stage1_SDF_offset_factor"] != factor or
                    [r["event"] for r in batch["rows"]] != route["cutting_prefix_ids"]):
                raise ValueError("分支尚未终态或输入身份错误")
            if not (index == 0 and factor == 0.0):
                run([AUDITOR, "--prepared", PREPARED, "--batch", branch, "--source-batch", REFERENCES / rid,
                     "--side-validation", SIDE, "--output", audit, "--kind", "unified"])
            ap = audit / "01-保存候选整面与材料侧独立复审.json"
            audited = read(ap)
            if audited["status"] != "completed" or audited["source_batch_sha256"] != sha(bp):
                raise ValueError("保存复审对象与终态批次未绑定")
            row.update(status="completed", batch_sha256=sha(bp), audit_sha256=sha(ap), summary=batch["summary"],
                       audit_summary=audited["summary"], event_outcomes=[{"event": r["event"], "status": r["status"]} for r in batch["rows"]],
                       actual_GPU_calls=sum("attempt" in r for r in batch["rows"]))
            save()
    report.update(status="completed", finished_beijing=now(), summary={"branches": len(rows), "planned_events": 42,
        "published": sum(r["summary"]["published"] for r in rows),
        "complete_routes": sum(r["summary"]["whole_route_complete"] for r in rows),
        "saved_reaudited_passed": sum(r["audit_summary"]["passed"] for r in rows),
        "actual_GPU_calls_including_inherited": sum(r["actual_GPU_calls"] for r in rows)})
    save()
    print(report["summary"], flush=True)


if __name__ == "__main__":
    main()
