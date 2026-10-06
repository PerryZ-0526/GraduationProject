"""只读核对已发布帧锚点运行记录，保留批次状态而不声明终态完成。"""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from audit_followup_candidate import sha256
from run_geometry_study import save, now


def check_anchor_record(record, ids):
    ids = np.asarray(ids)
    additions = []
    valid = True
    for update in record["updates"]:
        added = update["added_vertices"]
        valid = valid and bool(added) and len(added) == len(set(added))
        valid = valid and all(0 <= i < len(ids) and ids[i] == -1 for i in added)
        valid = valid and update.get("diff_call") == 1 and update.get("encoded_initial_exact") is True
        value = update.get("recomputed_energy")
        valid = valid and update.get("full_energy_recomputed") is True and update.get("recomputed_energy_finite") is True
        valid = valid and value is not None and np.isfinite(value)
        additions.extend(added)
    valid = valid and len(additions) == len(set(additions))
    valid = valid and record["current_anchor_count"] == record["initial_anchor_count"]+len(additions)
    return bool(valid)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    data = (args.run/"01-反馈执行与独立审计.json").read_bytes()
    report = json.loads(data)
    env = report["environment"]
    for name, field in (("anchored_geometry_system.py", "anchor_system_sha256"),
                        ("fixed_anchor_contract.py", "anchor_contract_sha256"),
                        ("run_anchored_worker.py", "actual_anchored_worker_sha256")):
        if sha256(args.run/name) != env[field]:
            raise ValueError("实际锚点源码或工作器摘要变化")
    rows = []
    for row in report["rows"]:
        if row["branch"] != "candidate" or row["status"] != "published_under_sampled_and_vertex_protocol":
            continue
        attempt = next(a for a in row["attempts"] if a["status"] == "accepted_sampled")
        folder = args.run/(row["route"]+"_"+row["event"]+"_candidate_"+row["selected_method"])
        path = folder/"anchor_updates.json"
        if path.exists():
            actual = json.loads(path.read_text(encoding="utf-8"))
            passed = actual == attempt.get("anchor_updates") and check_anchor_record(actual, attempt["vertex_original_ids"])
            rows.append(dict(route=row["route"], event=row["event"], passed=passed,
                anchor_record_sha256=sha256(path), updates=actual["updates"]))
        else:
            rows.append(dict(route=row["route"], event=row["event"],
                passed=attempt.get("projection") == "no_free_vertices_identity", kind="no_anchor_record_identity_required"))
    result = dict(time_beijing=now(), full_batch_status=report["status"],
        execution_record_snapshot_sha256=hashlib.sha256(data).hexdigest(), rows=rows,
        outputs=len(rows), passed=sum(r["passed"] for r in rows),
        scope="同次已发布帧锚点记录及源码摘要一致性；不替代保存网格、CUDA坐标独立核对或整批终态验收")
    if args.output.exists():
        raise FileExistsError(args.output)
    save(args.output, result)
    print(report["status"], result["passed"], "/", result["outputs"])
    if result["passed"] != result["outputs"]:
        raise SystemExit(1)
