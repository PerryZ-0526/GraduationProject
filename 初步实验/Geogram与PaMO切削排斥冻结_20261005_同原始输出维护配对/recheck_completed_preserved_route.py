"""复审运行中批次的已完成子路线，保留整批状态与冻结记录快照。"""
import argparse
from functools import partial
import json
from pathlib import Path
import recheck_shared_feedback as shared
from audit_followup_candidate import sha256
from preserved_controller_source import replace_once
from preserved_saved_binding import collect_certificates, mesh_valid_saved_binding
from run_constrained_batch import RemoteQuality
from run_geometry_study import save, now


def require_complete_route(report, route):
    expected = {(event, branch) for event in route["cutting_prefix_ids"] for branch in ("R", "full", "candidate")}
    rows = [r for r in report["rows"] if r["route"] == route["id"]]
    actual = [(r["event"], r["branch"]) for r in rows]
    if len(actual) != len(expected) or set(actual) != expected:
        raise ValueError("子路线记录未完整或存在重复")
    # 记录数量齐全仍可能含暂存状态，只有控制器定义的结束状态才可复审。
    finished = {"blocked_by_previous_failure", "union_failed", "reference_execution_failed",
        "reference_valid", "reference_alarm_unresolved", "contained_reused_parent", "geogram_failed",
        "source_cleanup_rejected", "maintenance_input_invalid", "all_registered_attempts_rejected",
        "published_under_sampled_and_vertex_protocol"}
    if any(r.get("status") not in finished for r in rows):
        raise ValueError("子路线存在未完成记录")
    return rows


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--route", required=True)
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    manifest_path = args.prepared/"01-完整范围冻结清单.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    route = next(r for r in manifest["routes"] if r["id"] == args.route)
    record_path = args.output/"01-反馈执行与独立审计.json"
    snapshot = args.output/("09-"+args.route+"-复审记录快照.json")
    if snapshot.exists():
        raise FileExistsError(snapshot)
    snapshot.write_bytes(record_path.read_bytes())
    report = json.loads(snapshot.read_text(encoding="utf-8"))
    if sha256(manifest_path) != report["manifest_sha256"]:
        raise ValueError("输入清单与同批记录不符")
    require_complete_route(report, route)
    source = Path(shared.__file__).read_text(encoding="utf-8")
    source = replace_once(source, 'record = json.loads(path.read_text(encoding="utf-8"))', 'record = FROZEN_REPORT')
    source = replace_once(source, 'record_sha256=sha256(path)', 'record_sha256=FROZEN_RECORD_SHA')
    source = replace_once(source, 'for route in manifest["routes"]:',
        'for route in manifest["routes"]:\n        if route["id"] != TARGET_ROUTE:\n            continue')
    source = replace_once(source,
        'reference = trimesh.load(reference_path, process=True, validate=True) if reference_path.exists() else None',
        'reference = load_bound_reference(reference_path, reference_row) if reference_path.exists() else None')
    source = replace_once(source, '(output / "04-保存输出父链与几何复审.json").write_text', '(output / RESULT_NAME).write_text')
    source = "from preserved_saved_binding import load_bound_reference\n"+source
    namespace = dict(__name__="completed_route_recheck", FROZEN_REPORT=report,
        FROZEN_RECORD_SHA=sha256(snapshot), TARGET_ROUTE=args.route,
        RESULT_NAME="10-"+args.route+"-已完成子路线保存复审.json")
    source_path = args.output/("completed_route_"+args.route+"_recheck.py")
    source_path.write_text(source, encoding="utf-8")
    exec(compile(source, str(source_path), "exec"), namespace)
    namespace["mesh_valid_exact_contacts"] = partial(mesh_valid_saved_binding, certificates=collect_certificates(report))
    engine = RemoteQuality(args.output, args.port)
    try:
        result = namespace["recheck"](args.prepared, args.output, engine)
        result.update(time_beijing=now(), full_batch_status=report["status"],
            scoped_route=args.route, planned_route_events=len(route["cutting_prefix_ids"]),
            scope="仅已完成子路线实际保存对象、精确证据、父链和双向探针复审；保留整批运行状态，不替代终态全分母复审")
        save(args.output/namespace["RESULT_NAME"], result)
        if result["passed"] != result["outputs"]:
            raise SystemExit(1)
    finally:
        engine.close()
