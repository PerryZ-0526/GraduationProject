"""汇总同冻结逐点版本八骨范围，逐个核对实际发布对象与独立复审绑定。"""

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
from zoneinfo import ZoneInfo


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--batches", type=Path, nargs=2, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest_path = args.prepared / "01-完整范围冻结清单.json"
    manifest = json.loads(manifest_path.read_text("utf8"))
    batches = [(p, json.loads((p / "01-公开骨完整范围与执行记录.json").read_text("utf8"))) for p in args.batches]
    snapshots = {d["snapshot_manifest_sha256"] for _, d in batches}
    registered = [rid for _, d in batches for rid in d["routes"]]
    if len(snapshots) != 1 or len(set(registered)) != 8 or len(registered) != 8:
        raise ValueError("必须是同源码冻结、无重复的完整八骨范围")
    if set(registered) != {r["id"] for r in manifest["routes"]}:
        raise ValueError("不能缺少冻结骨面或补入别的输入")
    rows, protocols = [], []
    for route in manifest["routes"]:
        rid = route["id"]
        batch = next(p for p, d in batches if rid in d["routes"])
        execution_path = batch / rid / "01-统一配置完整父反馈记录.json"
        entry = {"route": rid, "planned_events": len(route["cutting_prefix_ids"]), "status": "not_started",
                 "published": 0, "reaudited": 0, "complete": False}
        rows.append(entry)
        if not execution_path.exists():
            continue
        execution = json.loads(execution_path.read_text("utf8"))
        if execution["manifest_sha256"] != digest(manifest_path) or execution["snapshot_sha256"] not in snapshots:
            raise ValueError("逐路线输入或源码冻结不同")
        protocols.append(execution["protocol"])
        entry.update(status=execution["status"], execution_record_sha256=digest(execution_path))
        published = [r for r in execution["rows"] if r["status"] == "published"]
        # 正在执行的前缀单列，不冒充已完成独立复审的整条路线。
        entry["published"] = len(published)
        entry["actual_saved_hashes_match"] = all(digest(batch / rid / f'{rid}_{r["event"]}_candidate_boolean/candidate.obj') == r["output_sha256"] for r in published)
        if not entry["actual_saved_hashes_match"]:
            raise ValueError("已发布保存对象摘要不同")
        if execution["status"] != "completed_with_recorded_outcomes":
            continue
        if [r["event"] for r in execution["rows"]] != route["cutting_prefix_ids"]:
            raise ValueError("终态缺失或改变原计划事件顺序")
        if execution["summary"]["published"] != len(published):
            raise ValueError("终态发布摘要与逐行记录不一致")
        entry["complete"] = all(r["status"] == "published" for r in execution["rows"])
        audit_path = batch / (rid + "_保存复审") / "01-保存候选整面与材料侧独立复审.json"
        if not audit_path.exists():
            entry["status"] = "awaiting_saved_reaudit"
            continue
        audit = json.loads(audit_path.read_text("utf8"))
        if audit["status"] != "completed":
            entry["status"] = "saved_reaudit_running"
            continue
        if audit["source_batch_sha256"] != digest(execution_path):
            raise ValueError("保存复审不是本次实际父链记录")
        if {r["event"] for r in audit["rows"]} != {r["event"] for r in published}:
            raise ValueError("独立保存复审未覆盖全部真实发布对象")
        for row in audit["rows"]:
            if not all(row[k] for k in ["passed", "parent_hash_matches", "saved_hash_matches", "input_tool_hashes_match", "reference_hash_matches"]):
                raise ValueError("独立复审未通过实际父、工具、参照或保存对象绑定")
        entry.update(reaudited=len(audit["rows"]), reaudit_record_sha256=digest(audit_path),
                     outcomes=[{"event": r["event"], "status": r["status"]} for r in execution["rows"]])
    if any(p != protocols[0] for p in protocols[1:]):
        raise ValueError("逐路线实际协议不同，不能合成统一版本结果")
    terminal = all(r["status"] == "completed_with_recorded_outcomes" and r["reaudited"] == r["published"] for r in rows)
    now = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()
    args.output.mkdir(exist_ok=True)
    path = args.output / "01-同冻结八骨范围与证据核对.json"
    created = json.loads(path.read_text("utf8"))["生成时间"] if path.exists() else now
    record = {"生成时间": created, "修改时间及修改内容": now + "，核对当前实际证据，不改写原拒绝",
        "文档概述": "同冻结八骨32事件，运行前缀和完整终态分别标明", "索引目录": ["rows", "summary"],
        "status": "completed" if terminal else "incomplete_verified_snapshot", "snapshot_sha256": next(iter(snapshots)),
        "manifest_sha256": digest(manifest_path), "rows": rows, "summary": {"routes": 8,
            "planned_events": sum(r["planned_events"] for r in rows), "published_including_live_prefix": sum(r["published"] for r in rows),
            "saved_reaudited": sum(r["reaudited"] for r in rows), "terminal_routes": sum(r["status"] == "completed_with_recorded_outcomes" for r in rows),
            "complete_terminal_routes": sum(r["complete"] and r["status"] == "completed_with_recorded_outcomes" for r in rows),
            "continuous_target_distance_certified": False}}
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf8")
    print(record["status"], record["summary"], flush=True)


if __name__ == "__main__":
    main()
