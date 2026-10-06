"""核对双参照八骨的独立首骨、中断五骨和跨盘续跑两骨，不重复计数。"""

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
    for name in ("prepared", "single", "single-audit", "interrupted", "resumed", "recovery-audit", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    manifest_path = args.prepared / "01-完整范围冻结清单.json"
    manifest = json.loads(manifest_path.read_text("utf8"))
    single = json.loads((args.single / "01-统一配置完整父反馈记录.json").read_text("utf8"))
    rows, protocols, helper_hashes, snapshots = [], [], set(), set()
    for route in manifest["routes"]:
        rid = route["id"]
        candidates = [args.interrupted / rid, args.resumed / rid]
        if rid == single["selected_route"]:
            candidates.append(args.single)
        existing = [p for p in candidates if (p / "01-统一配置完整父反馈记录.json").exists()]
        if len(existing) > 1:
            raise ValueError("同一路线有多次执行，不能默默拼接或择优")
        entry = {"route": rid, "planned_events": len(route["cutting_prefix_ids"]),
                 "status": "not_started", "published": 0, "reaudited": 0, "complete": False}
        rows.append(entry)
        if not existing:
            continue
        folder = existing[0]
        path = folder / "01-统一配置完整父反馈记录.json"
        execution = json.loads(path.read_text("utf8"))
        if execution["manifest_sha256"] != digest(manifest_path):
            raise ValueError("输入清单不同")
        if not execution["environment"]["actual_parameters"].get("dual_reference_stop_required"):
            raise ValueError("不是实际双参照入口")
        helper_hashes.add(execution["environment"]["dual_reference_coverage_sha256"])
        snapshots.add(execution["snapshot_sha256"])
        protocols.append(execution["protocol"])
        entry.update(status=execution["status"], execution_path=str(path.resolve()), execution_sha256=digest(path))
        published = [r for r in execution["rows"] if r["status"] == "published"]
        entry["published"] = len(published)
        entry["finished_GPU_calls"] = sum("attempt" in r for r in execution["rows"])
        for row in published:
            candidate = folder / f'{rid}_{row["event"]}_candidate_boolean/candidate.obj'
            if digest(candidate) != row["output_sha256"]:
                raise ValueError("实际保存发布对象不同")
            if row["attempt"]["geometry_to_maintenance_source"]["probe_max_mm"] > .1 or row["cumulative_geometry"]["probe_max_mm"] > .1:
                raise ValueError("发布对象没有通过两种参照")
        if execution["status"] != "completed_with_recorded_outcomes":
            continue
        if [r["event"] for r in execution["rows"]] != route["cutting_prefix_ids"]:
            raise ValueError("终态原事件分母或顺序缺失")
        if execution["summary"]["published"] != len(published):
            raise ValueError("逐行计数与摘要不同")
        entry["complete"] = all(r["status"] == "published" for r in execution["rows"])
        if execution["summary"]["whole_route_complete"] != entry["complete"]:
            raise ValueError("路线完整标记不一致")
        # 单独首骨和磁盘恢复复审的路径显式给出，其他路线按真实执行根定位。
        if folder == args.single:
            audit_folder = args.single_audit
        elif rid.startswith("BP3D_FJ3259_"):
            audit_folder = args.recovery_audit
        else:
            audit_folder = folder.parent / (rid + "_保存复审")
        audit_path = audit_folder / "01-保存候选整面与材料侧独立复审.json"
        if not audit_path.exists():
            entry["status"] = "awaiting_reaudit"
            continue
        audit = json.loads(audit_path.read_text("utf8"))
        if audit["status"] != "completed":
            entry["status"] = "reaudit_running"
            continue
        if audit["source_batch_sha256"] != digest(path):
            raise ValueError("复审不是该实际父链执行记录")
        if {r["event"] for r in audit["rows"]} != {r["event"] for r in published}:
            raise ValueError("复审缺少实际发布对象")
        for row in audit["rows"]:
            if not all(row[k] is True for k in ("passed", "parent_hash_matches", "saved_hash_matches", "input_tool_hashes_match", "reference_hash_matches")):
                raise ValueError("复审或哈希绑定未通过")
        entry.update(reaudited=len(audit["rows"]), audit_path=str(audit_path.resolve()), audit_sha256=digest(audit_path),
                     outcomes=[{"event": r["event"], "status": r["status"]} for r in execution["rows"]])
    if len(snapshots) != 1 or len(helper_hashes) != 1 or any(p != protocols[0] for p in protocols[1:]):
        raise ValueError("实际冻结源码、双参照实现或协议不一致")
    terminal = all(r["status"] == "completed_with_recorded_outcomes" and r["published"] == r["reaudited"] for r in rows)
    now = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()
    args.output.mkdir(exist_ok=True)
    path = args.output / "01-双参照中断恢复八骨完整证据核对.json"
    created = json.loads(path.read_text("utf8"))["生成时间"] if path.exists() else now
    report = {"生成时间": created, "修改时间及修改内容": now + "，核对当前实际文件与保存复审",
        "文档概述": "原八骨32事件，不重跑、不择优，运行前缀不冒充终态",
        "索引目录": ["rows", "summary"], "status": "completed" if terminal else "incomplete_verified_snapshot",
        "manifest_sha256": digest(manifest_path), "snapshot_sha256": next(iter(snapshots)),
        "dual_reference_helper_sha256": next(iter(helper_hashes)), "rows": rows,
        "summary": {"routes": 8, "planned_events": sum(r["planned_events"] for r in rows),
            "published_including_live_prefix": sum(r["published"] for r in rows),
            "saved_reaudited": sum(r["reaudited"] for r in rows),
            "finished_GPU_calls": sum(r.get("finished_GPU_calls", 0) for r in rows),
            "terminal_routes": sum(r["status"] == "completed_with_recorded_outcomes" for r in rows),
            "complete_terminal_routes": sum(r["complete"] and r["status"] == "completed_with_recorded_outcomes" for r in rows),
            "continuous_target_distance_certified": False}}
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf8")
    print(report["status"], report["summary"], flush=True)


if __name__ == "__main__":
    main()
