"""完整闭环批次：有效候选才回灌，扩域及原版回退成本全部保留。"""

import argparse
import json
from pathlib import Path
from time import perf_counter

import numpy as np
import pyvista as pv
import trimesh

from audit_followup_candidate import sha256
from audit_pamo_outputs import as_polydata, reference_audit
from geometry_preservation_audit import mesh_valid, MeshDistance, preservation, replay_primitives
from generate_followup_reference import reference_mesh
from locality_masks import save_obj_fp64
from run_constrained_batch import RemoteQuality, audit_candidate, HERE
from run_geometry_study import execute, retrieve, save, now, GEO
from run_followup_geogram import contained
from locality_diagnostic import source_region, verify_labels
from locality_cleanup import clean_provenance

PROVENANCE = "/root/autodl-tmp/graduation_project/locality_20261004_021939/geogram_provenance"
VALID_SOURCE_BITS = (1, 2)  # 新入口可显式扩展共同来源，历史协议默认不变。
REFERENCE_RECOVERY = None  # 显式新入口可恢复独立参照，历史默认流程保持原样。


def global_geometry(candidate, reference):
    """面积样本之外加入全部顶点探针，记录漏检窄区的数值见证。"""
    source = as_polydata(candidate)
    target = reference if isinstance(reference, pv.PolyData) else as_polydata(reference)
    sampled = reference_audit(source, target)
    forward = MeshDistance(target)(source.points)
    reverse = MeshDistance(source)(target.points)
    vertex_max = max(float(forward.max()), float(reverse.max()))
    return {"sampled": sampled, "all_vertices_probe_max_mm": vertex_max,
            "probe_max_mm": max(vertex_max, sampled["sampled_max_mm"]),
            "continuous_geometry_certified": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--split", choices=("development", "evaluation", "long", "application"), required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    manifest_path = args.prepared / "01-完整范围冻结清单.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    routes = [r for r in manifest["routes"] if r["split"] == args.split]
    for route in routes:
        for name, expected in [(route["initial_mesh"], route["initial_mesh_sha256"]),
                               *[(t["mesh"], t["sha256"]) for t in route["prefix_tools"]]]:
            if sha256(args.prepared / "inputs" / name) != expected:
                raise ValueError("冻结输入变化")
    args.output.mkdir(parents=True)
    report = {"time_beijing": now(), "split": args.split, "manifest_sha256": sha256(manifest_path),
              "script_sha256": sha256(Path(__file__)), "audit_sha256": sha256(HERE / "geometry_preservation_audit.py"),
              "status": "running", "rows": [], "initial_audits": {}}
    record = args.output / "01-反馈执行与独立审计.json"
    engine = RemoteQuality(args.output, args.port)
    try:
        report["environment"] = engine.setup()
        report["environment"]["provenance_binary_sha256"] = execute(engine.client, ["sha256sum", PROVENANCE])["stdout"].split()[0]
        # 先保存方法及编译冻结记录，再打开新独立候选输出。
        save(args.output / "02-本批方法冻结.json", {"time_beijing": now(), "environment": report["environment"],
            "parameters": {"iterations": 3, "rings": 2, "expanded_rings": 4, "projection_iterations": 5,
                           "geometry_policy": "report_only_no_distance_stop", "geometry_check": "8192_area_samples_and_all_vertices",
                           "fallback": "expanded_once_then_original_full"},
            "input_manifest_sha256": sha256(manifest_path)})
        save(record, report)
        for route in routes:
            rid = route["id"]
            initial_path = args.prepared / "inputs" / route["initial_mesh"]
            initial = trimesh.load(initial_path, force="mesh", process=False)
            valid, checks = mesh_valid(initial)
            report["initial_audits"][rid] = checks
            parent_paths = {"full": initial_path, "candidate": initial_path}
            blocked = {"full": not valid, "candidate": not valid, "R": not valid}
            versions = {"full": 0, "candidate": 0}
            initial_remote = engine.remote + "/" + rid + "_initial.obj"
            engine.sftp.put(str(initial_path), initial_remote)
            union_remote = None
            tools = {r["event_id"]: r for r in route["prefix_tools"]}
            reference_cache = {}
            retained = []
            events = {e["id"]: e for e in route["events"]}
            for eid in route["cutting_prefix_ids"]:
                primitive = replay_primitives(route, eid)[-1]
                clip_radius = events[eid].get("plan_clip_radius_mm")
                previous_segments = [(r["start"], r["end"]) for r in retained
                    if r["radius"] == primitive["radius"] and r["clip_radius"] == clip_radius]
                reuse = contained(primitive["start"].tolist(), primitive["end"].tolist(), previous_segments)
                tool_path = args.prepared / "inputs" / tools[eid]["mesh"]
                tool_remote = engine.remote + "/" + rid + "_" + eid + "_tool.obj"
                engine.sftp.put(str(tool_path), tool_remote)
                reference = None
                rrow = {"route": rid, "event": eid, "branch": "R", "status": "blocked_by_previous_failure"}
                report["rows"].append(rrow)
                folder = args.output / (rid + "_" + eid + "_reference")
                folder.mkdir()
                if not blocked["R"]:
                    if union_remote is None:
                        union_remote = tool_remote
                    elif not reuse:
                        new_union = engine.remote + "/" + rid + "_" + eid + "_union.obj"
                        log = new_union + ".log"
                        result = execute(engine.client, [GEO, union_remote, tool_remote, new_union, "--operation", "union"], log, timeout=120)
                        retrieve(engine.client, engine.sftp, log, folder / "union.log")
                        rrow["union_run"] = result
                        if result["returncode"]:
                            blocked["R"] = True
                            rrow["status"] = "union_failed"
                        else:
                            union_remote = new_union
                    if not blocked["R"]:
                        remote_ref = engine.remote + "/" + rid + "_" + eid + "_R.obj"
                        log = remote_ref + ".log"
                        result = execute(engine.client, [GEO, initial_remote, union_remote, remote_ref], log, timeout=120)
                        retrieve(engine.client, engine.sftp, log, folder / "reference.log")
                        rrow["run"] = result
                        if result["returncode"]:
                            blocked["R"] = True
                            rrow["status"] = "reference_execution_failed"
                        else:
                            retrieve(engine.client, engine.sftp, remote_ref, folder / "reference.obj")
                            mesh = trimesh.load(folder / "reference.obj", force="mesh", process=True, validate=True)
                            valid_ref, metrics = mesh_valid(mesh)
                            rrow["metrics"] = metrics
                            rrow["status"] = "reference_valid" if valid_ref else "reference_alarm_unresolved"
                            if valid_ref:
                                reference = mesh
                            else:
                                blocked["R"] = True
                if reference is None and REFERENCE_RECOVERY is not None and not (blocked["full"] and blocked["candidate"]):
                    # 保留原参照失败记录，再独立从初态和截至当前的工具重放；不借用候选父链。
                    recovered, recovery = REFERENCE_RECOVERY(engine,args.prepared,route,eid,initial_remote,folder,reuse)
                    rrow["recovery"] = recovery
                    if recovered is not None:
                        reference = recovered
                        rrow.update(primary_status=rrow["status"],status="reference_valid",
                                    reference_used_file="validated_reference.obj",metrics=recovery["validated_metrics"])
                        reference_cache[eid] = {"kind":"independent_sequential_replay_recovered", "sha256":sha256(folder / "validated_reference.obj")}
                if reference is None and route["body"] != "ct" and not (blocked["full"] and blocked["candidate"]):
                    # 解析离散参照独立生成，不借用候选网格，也不改变物理输入。
                    surface, diagnostics = reference_mesh(route, eid, .025)
                    surface.save(folder / "analytic_reference.vtp")
                    reference = surface
                    reference_cache[eid] = {"kind": "analytic_field_discrete_isosurface", "diagnostics": diagnostics,
                                            "sha256": sha256(folder / "analytic_reference.vtp")}
                for branch in ("full", "candidate"):
                    row = {"route": rid, "event": eid, "branch": branch,
                           "status": "blocked_by_previous_failure", "published_version": versions[branch]}
                    report["rows"].append(row)
                    if blocked[branch]:
                        continue
                    if reuse:
                        # 同半径、同计划裁剪下被旧扫掠包含的原语不重复优化，也不虚增网格版本。
                        row.update(status="contained_reused_parent", parent_sha256=sha256(parent_paths[branch]),
                                   output_sha256=sha256(parent_paths[branch]), state_mesh_version一致=True)
                        continue
                    started = perf_counter()
                    parent = parent_paths[branch]
                    row["parent_sha256"] = sha256(parent)
                    row["tool_sha256"] = sha256(tool_path)
                    stem = rid + "_" + eid + "_" + branch
                    inputs = args.output / (stem + "_input")
                    inputs.mkdir()
                    parent_remote = engine.remote + "/" + stem + "_parent.obj"
                    source_remote = engine.remote + "/" + stem + "_source.obj"
                    labels_remote = engine.remote + "/" + stem + "_labels.json"
                    engine.sftp.put(str(parent), parent_remote)
                    log = source_remote + ".log"
                    result = execute(engine.client, [PROVENANCE, parent_remote, tool_remote, source_remote, labels_remote,
                        "--no-simplify"], log, timeout=120)
                    retrieve(engine.client, engine.sftp, log, inputs / "geogram.log")
                    row["geogram_run"] = result
                    if result["returncode"]:
                        row["status"], blocked[branch] = "geogram_failed", True
                        continue
                    for remote_name, name in ((source_remote, "source.obj"), (labels_remote, "labels.json")):
                        retrieve(engine.client, engine.sftp, remote_name, inputs / name)
                    source = trimesh.load(inputs / "source.obj", force="mesh", process=False)
                    bits = json.loads((inputs / "labels.json").read_text())["operand_bits"]
                    # 两条分支统一清理数值重复点；原始布尔文件保留，来源随面同步筛选。
                    try:
                        source, bits, cleanup = clean_provenance(source, bits)
                    except ValueError as error:
                        row["cleanup_error"] = str(error)
                        row["status"], blocked[branch] = "source_cleanup_rejected", True
                        continue
                    row["source_cleanup"] = cleanup
                    maintenance_source = inputs / "clean_source.obj"
                    maintenance_labels = inputs / "clean_labels.json"
                    save_obj_fp64(source, maintenance_source)
                    save(maintenance_labels, {"operand_bits": bits.tolist()})
                    input_valid, input_metrics = mesh_valid(source)
                    row["input_metrics"] = input_metrics
                    if not input_valid or input_metrics["fp32_zero_area_faces"]:
                        row["status"], blocked[branch] = "maintenance_input_invalid", True
                        continue
                    # 按入口冻结的来源协议判定，不将共同来源强制映射到单来源。
                    labels_valid = len(bits) == len(source.faces) and all(b in VALID_SOURCE_BITS for b in bits)
                    if labels_valid:
                        _, _, seam = source_region(source, bits)
                        provenance_check = verify_labels(source, bits,
                            trimesh.load(parent, force="mesh", process=False),
                            trimesh.load(tool_path, force="mesh", process=False), seam)
                        row["source_label_numerical_validation"] = provenance_check
                        labels_valid = provenance_check["passed_1e_8_mm_numerical_check"]
                    row["source_labels_valid"] = labels_valid
                    # 来源不可信时保留几何输入，回退原版而不猜测活动域。
                    methods = ("full",) if branch == "full" or not labels_valid else ("boolean", "expanded", "full")
                    row["attempts"] = []
                    accepted = None
                    for method in methods:
                        destination = args.output / (stem + "_" + method)
                        attempt = engine.run(maintenance_source, maintenance_labels, tool_path, method, destination)
                        attempt = audit_candidate(maintenance_source, tool_path, maintenance_labels, destination, attempt)
                        row["attempts"].append(attempt)
                        if attempt["status"] != "accepted_sampled":
                            continue
                        candidate = trimesh.load(destination / "candidate.obj", force="mesh", process=False)
                        if reference is None:
                            attempt["status"] = "reference_unavailable"
                            continue
                        geometry = global_geometry(candidate, reference)
                        attempt["cumulative_geometry"] = geometry
                        attempt["reference_kind"] = reference_cache.get(eid, {}).get("kind", "cumulative_same_discrete_tools")
                        # 几何偏差仅统计，不因超过距离阈值阻断材料反馈；保留其他有效性检查。
                        attempt["geometry_policy"] = "report_only_no_distance_stop"
                        attempt["preservation"] = preservation(candidate, initial, route, eid)
                        accepted = destination / "candidate.obj"
                        row["selected_method"] = method
                        row["cumulative_geometry"] = geometry
                        row["preservation"] = attempt["preservation"]
                        row["output_sha256"] = sha256(accepted)
                        row["signed_removed_volume_mm3"] = float(initial.volume - candidate.volume)
                        break
                    if accepted is None:
                        blocked[branch] = True
                        row["status"] = "all_registered_attempts_rejected"
                    else:
                        parent_paths[branch] = accepted
                        versions[branch] += 1
                        row["published_version"] = versions[branch]
                        row["state_mesh_version一致"] = True
                        row["status"] = "published_under_sampled_and_vertex_protocol"
                    row["frame_wall_including_audit_ms"] = (perf_counter() - started) * 1000
                    save(record, report)
                    print(rid, eid, branch, row["status"], row.get("selected_method"), flush=True)
                save(record, report)
                if not reuse:
                    retained.append({"start": primitive["start"].tolist(), "end": primitive["end"].tolist(),
                                     "radius": primitive["radius"], "clip_radius": clip_radius})
            report.setdefault("route_event_policy", {})[rid] = {"non_cutting_or_rejected_events": [e["id"]
                for e in route["events"] if e["id"] not in route["cutting_prefix_ids"]],
                "behavior": "no_geometry_update_keep_last_published_version", "final_versions": versions}
            save(record, report)
        report.update(status="completed_with_recorded_failures", finished_beijing=now())
        save(record, report)
    finally:
        engine.close()


if __name__ == "__main__":
    main()
