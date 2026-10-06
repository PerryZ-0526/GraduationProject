"""汇总冻结C1试运行的逐帧哈希、审计结果和事件处理。"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    routes = []
    for route in manifest["routes"]:
        kind = "crossing" if route["category"] == "crossing" else "stop_resume"
        expected_parent = route["initial_mesh_sha256"]
        latest_timestamp = None
        events = []
        for event in route["events"]:
            timestamp = event["timestamp_ms"]
            if latest_timestamp is not None and timestamp <= latest_timestamp:
                events.append({"event": event["id"], "status": "late_rejected",
                               "published_mesh_sha256": expected_parent})
                continue
            latest_timestamp = timestamp
            if not event["cutting"]:
                events.append({"event": event["id"], "status": "not_cutting",
                               "published_mesh_sha256": expected_parent})
                continue
            stem = f"{kind}_{event['id']}"
            directory = args.results / stem
            step = json.loads((directory / "step.json").read_text(encoding="utf-8"))
            audit = json.loads((directory / "audit.json").read_text(encoding="utf-8"))
            parent_matched = step["parent_sha256"] == expected_parent
            output_matched = (step["pamo"]["sha256"] == sha256(directory / "pamo.obj") and
                              step["geogram"]["sha256"] == sha256(directory / "geogram.obj"))
            passed = bool(parent_matched and output_matched and
                          step["geogram"]["returncode"] == 0 and
                          step["pamo"]["returncode"] == 0 and
                          audit["accepted_under_sampled_protocol_with_vertex_check"])
            distribution = audit["quality_distribution"]
            events.append({
                "event": event["id"], "status": "sampled_protocol_passed" if passed else "failed",
                "parent_sha256": step["parent_sha256"], "parent_chain_matched": parent_matched,
                "geogram_sha256": step["geogram"]["sha256"],
                "pamo_sha256": step["pamo"]["sha256"], "output_hash_matched": output_matched,
                "geogram_wall_ms": step["geogram"]["wall_ms"],
                "pamo_wall_ms": step["pamo"]["wall_ms"],
                "audit_wall_ms": audit["metrics"]["audit_wall_ms"],
                "faces": distribution["total_faces"],
                "invalid_faces": distribution["invalid_faces"],
                "angle_below_10_fraction": distribution["angle_below_10_deg"]["fraction"],
                "angle_below_5_fraction": distribution["angle_below_5_deg"]["fraction"],
                "angle_below_1_fraction": distribution["angle_below_1_deg"]["fraction"],
                "high_quality_fraction": distribution["high_quality_25_deg_q_0_4"]["fraction"],
                "sampled_max_mm": audit["metrics"]["sampled_reference_geometry"]["sampled_max_mm"],
                "topology_passed": audit["topology_passed_with_vertex_check"],
            })
            if passed:
                expected_parent = step["pamo"]["sha256"]
            else:
                break
        cutting = [item for item in events if item["status"] in
                   {"sampled_protocol_passed", "failed"}]
        routes.append({"route": route["id"], "events": events,
                       "cutting_passed": sum(item["status"] == "sampled_protocol_passed"
                                             for item in cutting),
                       "cutting_expected": len(route["cutting_prefix_ids"]),
                       "final_published_mesh_sha256": expected_parent})
    report = {
        "schema_version": 1,
        "time_beijing": datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S"),
        "manifest_sha256": sha256(args.manifest), "variant": "P",
        "acceptance_scope": "开发输入上的拓扑和离散参照双向抽样诊断；非连续几何证书",
        "routes": routes,
    }
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"routes": [(item["route"], item["cutting_passed"],
                                   item["cutting_expected"]) for item in routes]},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
