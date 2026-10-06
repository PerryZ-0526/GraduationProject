"""只读复核已保存的自交报警输入，不把检查器修订冒充新增序列通过。"""

import argparse
import json
from pathlib import Path
import trimesh

from geometry_preservation_audit import mesh_valid
from run_geometry_study import now, save
from audit_followup_candidate import sha256


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    record = args.runs / "01-连续几何执行与审计.json"
    study = json.loads(record.read_text(encoding="utf-8"))
    result = {"time_beijing": now(), "original_record_sha256": sha256(record), "rows": []}
    for row in study["rows"]:
        if row["status"] not in ("pamo_input_invalid", "reference_topology_invalid"):
            continue
        folder = args.runs / row["route"] / row["event"]
        path = folder / ("R.obj" if row["branch"] == "R" else row["branch"] + "_clean.obj")
        mesh = trimesh.load(path, force="mesh", process=row["branch"] == "R", validate=row["branch"] == "R")
        valid, metrics = mesh_valid(mesh)
        result["rows"].append({"route": row["route"], "event": row["event"], "branch": row["branch"],
            "mesh_sha256": sha256(path), "valid_after_alarm_review": valid,
            "original_status": row["status"], "metrics": metrics,
            "subsequent_pamo_and_feedback_rerun": False})
    save(args.output, result)
    print("reviewed", len(result["rows"]), "cleared", sum(r["valid_after_alarm_review"] for r in result["rows"]))


if __name__ == "__main__":
    main()
