"""审计BVH剖析输出，并汇总构建、更新、查询的同步计时。"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import statistics

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
    parser.add_argument("--profiles", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    reference_info = {}
    for item in manifest["references"]:
        kind = "crossing" if "crossing" in item["route"] else "stop_resume"
        reference_info[f"{kind}_{item['event']}"] = item
    report = {
        "time_beijing": datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S"),
        "manifest_sha256": sha256(args.manifest),
        "rows": [],
    }
    for directory in sorted(args.profiles.glob("bvh_profile_*_20260929")):
        case = directory.name.removeprefix("bvh_profile_").removesuffix("_20260929")
        if case not in reference_info:
            raise ValueError(f"未知开发输入: {case}")
        profile = json.loads((directory / "profile.json").read_text(encoding="utf-8"))
        source = args.inputs / case / "geogram.obj"
        candidate = directory / "mesh.obj"
        info = reference_info[case]
        reference = args.references / info["mesh"]
        if (sha256(source) != profile["input_sha256"] or
                sha256(candidate) != profile["output_sha256"] or
                sha256(reference) != info["sha256"]):
            raise ValueError(f"输入、输出或参照哈希不符: {case}")
        mesh = trimesh.load(candidate, force="mesh", process=False)
        metrics = audit_one(source, candidate, reference)
        quality = quality_distribution(mesh)
        components = len(mesh.split(only_watertight=False))
        manifold = vertex_manifold_closed(np.asarray(mesh.faces))
        accepted = bool(metrics["topology_passed"] and metrics["sampled_geometry_passed"] and
                        quality["invalid_faces"] == 0 and components == 1 and manifold)
        operations = profile["operations"]
        group_ms = {
            group: sum(item["sum_ms"] for name, item in operations.items() if name.startswith(prefix))
            for group, prefix in (("build", "build_"), ("update", "update_"), ("query", "query_"))
        }
        row = {"case": case, "accepted_sampled": accepted,
               "input_sha256": profile["input_sha256"],
               "output_sha256": profile["output_sha256"],
               "run_ms": profile["run_ms"],
               "construct_ms": profile["construct_ms"],
               "register_mesh_ms": operations["register_mesh_total"]["sum_ms"],
               "contact_count_max": profile["contact_count_max"],
               "group_ms": group_ms,
               "bvh_group_share_of_run": sum(group_ms.values()) / profile["run_ms"],
               "operations": operations,
               "sampled_max_mm": metrics["sampled_reference_geometry"]["sampled_max_mm"],
               "quality": quality,
               "components": components,
               "vertex_manifold": manifold}
        report["rows"].append(row)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(case, accepted, flush=True)
    if len(report["rows"]) != 8:
        raise ValueError("BVH开发输入数量不等于8")
    rows = report["rows"]
    report["summary"] = {
        "accepted_sampled": sum(row["accepted_sampled"] for row in rows),
        "contact_count_max": max(row["contact_count_max"] for row in rows),
        "worst_sampled_max_mm": max(row["sampled_max_mm"] for row in rows),
        "group_ms": {group: {"min": min(row["group_ms"][group] for row in rows),
                             "mean": statistics.mean(row["group_ms"][group] for row in rows),
                             "max": max(row["group_ms"][group] for row in rows)}
                     for group in ("build", "update", "query")},
        "bvh_group_share_of_run": {
            "min": min(row["bvh_group_share_of_run"] for row in rows),
            "mean": statistics.mean(row["bvh_group_share_of_run"] for row in rows),
            "max": max(row["bvh_group_share_of_run"] for row in rows),
        },
    }
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
