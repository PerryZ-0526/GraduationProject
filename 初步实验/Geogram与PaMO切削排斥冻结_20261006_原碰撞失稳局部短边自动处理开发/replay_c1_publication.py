"""将已审计C1帧按到达顺序重放为同版本网格与名义状态。"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path

import trimesh


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def volume(path: Path) -> float:
    mesh = trimesh.load(path, force="mesh", process=False)
    if not mesh.is_watertight or not mesh.is_winding_consistent:
        raise ValueError(f"体积输入非闭合一致实体: {path}")
    return float(mesh.volume)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--initials", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    rows = []
    for route in manifest["routes"]:
        initial = args.initials / route["initial_mesh"]
        if sha256(initial) != route["initial_mesh_sha256"]:
            raise ValueError(f"初态哈希不符: {route['id']}")
        initial_volume = volume(initial)
        published_hash = sha256(initial)
        published_volume = initial_volume
        published_version = 0
        latest_timestamp = None
        route_rows = []
        for event in route["events"]:
            timestamp = event["timestamp_ms"]
            status = ""
            if latest_timestamp is not None and timestamp <= latest_timestamp:
                status = "late_rejected"
            elif not event["cutting"]:
                latest_timestamp = timestamp
                status = "not_cutting"
            else:
                latest_timestamp = timestamp
                kind = "crossing" if route["category"] == "crossing" else "stop_resume"
                directory = args.results / f"{kind}_{event['id']}"
                step = json.loads((directory / "step.json").read_text(encoding="utf-8"))
                audit = json.loads((directory / "audit.json").read_text(encoding="utf-8"))
                mesh = directory / "pamo.obj"
                valid = (step["parent_sha256"] == published_hash and
                         step["pamo"]["sha256"] == sha256(mesh) and
                         step["geogram"]["returncode"] == 0 and
                         step["pamo"]["returncode"] == 0 and
                         audit["accepted_under_sampled_protocol_with_vertex_check"])
                if not valid:
                    status = "rejected_audit_or_chain"
                else:
                    published_hash = sha256(mesh)
                    published_volume = volume(mesh)
                    published_version += 1
                    status = "published_under_sampled_protocol"
            route_rows.append({
                "event": event["id"], "timestamp_ms": timestamp,
                "status": status, "published_version": published_version,
                "mesh_sha256": published_hash, "state_mesh_sha256": published_hash,
                "nominal_mesh_volume_mm3": published_volume,
                "nominal_removed_volume_mm3": initial_volume - published_volume,
                "plan_completion_fraction": None,
            })
            if status == "rejected_audit_or_chain":
                break
        rows.append({"route": route["id"], "initial_volume_mm3": initial_volume,
                     "events": route_rows})
    report = {
        "schema_version": 1,
        "time_beijing": datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S"),
        "manifest_sha256": sha256(args.manifest),
        "state_scope": "离线重放；网格有向体积的名义去除量；非计划内完成度或误差证书",
        "routes": rows,
    }
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({item["route"]: [(row["event"], row["status"],
                                        row["published_version"]) for row in item["events"]]
                      for item in rows}, ensure_ascii=False))


if __name__ == "__main__":
    main()
