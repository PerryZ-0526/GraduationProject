"""审计常驻和独立进程性能对照的全部输出网格。"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path

import numpy as np
import trimesh

from audit_followup_candidate import quality_distribution, vertex_manifold_closed
from sys import path as sys_path

sys_path.insert(0, str(Path(__file__).resolve().parent.parent / "共同运动记录与方法对照"))
from audit_pamo_outputs import audit_one


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--references", type=Path, required=True)
    parser.add_argument("--isolated", type=Path, required=True)
    parser.add_argument("--resident", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    reference_info = {}
    for item in manifest["references"]:
        kind = "crossing" if "crossing" in item["route"] else "stop_resume"
        reference_info[f"{kind}_{item['event']}"] = item
    report = {"schema_version": 1,
              "time_beijing": datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S"),
              "manifest_sha256": sha256(args.manifest), "rows": []}
    directories = [args.isolated] + ([args.resident] if args.resident else [])
    for directory in directories:
        execution = json.loads((directory / "report.json").read_text(encoding="utf-8"))
        mode = execution["mode"]
        if execution.get("module_path"):
            mode += "_stage3_3"
        for row in execution["rows"]:
            stem = f"r{row['round']}_{row['case']}"
            candidate = directory / f"{stem}.obj"
            source = args.inputs / row["case"] / "geogram.obj"
            info = reference_info[row["case"]]
            reference = args.references / info["mesh"]
            if sha256(candidate) != row["output_sha256"] or sha256(reference) != info["sha256"]:
                raise ValueError(f"输出或参照摘要不符: {stem}")
            mesh = trimesh.load(candidate, force="mesh", process=False)
            metrics = audit_one(source, candidate, reference)
            distribution = quality_distribution(mesh)
            components = len(mesh.split(only_watertight=False))
            vertex_manifold = vertex_manifold_closed(np.asarray(mesh.faces))
            accepted = bool(metrics["topology_passed"] and metrics["sampled_geometry_passed"] and
                            distribution["invalid_faces"] == 0 and components == 1 and vertex_manifold)
            report["rows"].append({
                "mode": mode, "round": row["round"], "case": row["case"],
                "candidate_sha256": row["output_sha256"], "accepted_sampled": accepted,
                "components": components, "vertex_manifold": vertex_manifold,
                "topology": metrics["output_topology"], "quality": distribution,
                "sampled_max_mm": metrics["sampled_reference_geometry"]["sampled_max_mm"],
                "wall_ms": row["wall_ms"],
            })
            args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                                   encoding="utf-8")
            print(mode, row["round"], row["case"], accepted, flush=True)


if __name__ == "__main__":
    main()
