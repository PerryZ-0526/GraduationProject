"""重新加载已发布切削排斥网格，核对真实父链、整面支撑、锚点及累计参照。"""

import argparse
import json
from pathlib import Path

import trimesh

from audit_followup_candidate import sha256, quality_distribution
from audit_cut_delivery import certify, probes
from exact_alarm_contact import mesh_valid_exact_contacts
from run_constrained_feedback import global_geometry
from run_geometry_study import save, now


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(exist_ok=False)
    manifest = json.loads((args.prepared / "01-完整范围冻结清单.json").read_text("utf8"))
    batch = json.loads((args.batch / "01-反馈执行与独立审计.json").read_text("utf8"))
    if batch["status"] == "running":
        raise ValueError("完整终态尚未确认，不能生成最终复审")
    routes = {r["id"]: r for r in manifest["routes"]}
    parents = {(r["id"], branch): r["initial_mesh_sha256"] for r in routes.values() for branch in ("full", "candidate")}
    report = {"生成时间": now(), "修改时间及修改内容": "首次生成，重新加载终态保存对象",
              "文档概述": "实际发布网格与原记录对拍；累计目标距离仍为有限探针",
              "索引目录": ["rows", "summary"], "batch_sha256": sha256(args.batch / "01-反馈执行与独立审计.json"),
              "manifest_sha256": sha256(args.prepared / "01-完整范围冻结清单.json"), "rows": [], "status": "running"}
    target = args.output / "01-保存网格与整面排斥独立复审.json"
    (args.output / Path(__file__).name).write_bytes(Path(__file__).read_bytes())
    for row in batch["rows"]:
        if row.get("branch") not in ("full", "candidate") or row["status"] != "published_under_sampled_and_vertex_protocol":
            continue
        rid, event, branch = row["route"], row["event"], row["branch"]
        route = routes[rid]
        folder = args.batch / f"{rid}_{event}_{branch}_{row['selected_method']}"
        path = folder / "candidate.obj"
        mesh = trimesh.load(path, force="mesh", process=False)
        valid, checks = mesh_valid_exact_contacts(mesh)
        prefix = set(route["cutting_prefix_ids"][:route["cutting_prefix_ids"].index(event) + 1])
        tools = [args.prepared / "inputs" / t["mesh"] for t in route["prefix_tools"] if t["event_id"] in prefix]
        tool_meshes = [trimesh.load(p, force="mesh", process=False) for p in tools]
        reference_folder = args.batch / f"{rid}_{event}_reference"
        reference_path = reference_folder / "validated_reference.obj"
        if not reference_path.exists():
            reference_path = reference_folder / "reference.obj"
        reference = trimesh.load(reference_path, force="mesh", process=True, validate=True)
        geometry = global_geometry(mesh, reference)
        attempt = next(a for a in row["attempts"] if a["method"] == row["selected_method"])
        exact = attempt["exact_embedding"]
        entry = {"route": rid, "event": event, "branch": branch, "mesh_valid": valid, "checks": checks,
                 "parent_hash_matches": parents[(rid, branch)] == row["parent_sha256"],
                 "saved_hash_matches": sha256(path) == row["output_sha256"],
                 "exact_embedding_bound_to_saved_object": exact.get("embedded_closed", False) and exact["saved_sha256"] == sha256(path),
                 "reference_sha256": sha256(reference_path), "geometry": geometry,
                 "probes": probes(mesh, tool_meshes), "quality": quality_distribution(mesh)}
        if branch == "candidate":
            details = attempt["cut_exclusion"]
            entry.update(exact_face_anchor_reaudit=certify(mesh, tool_meshes, details),
                         cumulative_tool_hashes_match=[sha256(p) for p in tools] == details["cumulative_tool_sha256"],
                         reference_hash_matches=sha256(reference_path) == details["cumulative_reference_sha256"])
        entry["passed"] = bool(valid and entry["parent_hash_matches"] and entry["saved_hash_matches"]
            and entry["exact_embedding_bound_to_saved_object"] and geometry["probe_max_mm"] <= .1
            and (branch != "candidate" or (entry["exact_face_anchor_reaudit"]["passed"]
                and entry["cumulative_tool_hashes_match"] and entry["reference_hash_matches"])))
        report["rows"].append(entry)
        parents[(rid, branch)] = row["output_sha256"]
        save(target, report)
    report.update(status="completed", finished_beijing=now(), summary={"published_meshes": len(report["rows"]),
        "passed": sum(row["passed"] for row in report["rows"]),
        "candidate_exact_face_anchor_passed": sum(row["branch"] == "candidate" and row["passed"] for row in report["rows"]),
        "continuous_target_distance_certified": False})
    save(target, report)
    print(report["summary"], flush=True)


if __name__ == "__main__":
    main()
