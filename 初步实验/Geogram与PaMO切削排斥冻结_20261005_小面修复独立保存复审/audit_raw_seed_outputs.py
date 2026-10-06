"""独立复审分布观察输出，几何误差仅统计，不改变原排斥及嵌入门槛。"""

import argparse
from fractions import Fraction
import getpass
import json
from pathlib import Path
import sys

import numpy as np
import trimesh
from exact_oriented_surface_identity import exact_oriented_surface_identity

# 审计与开发版本共用不可变数值协议，不能读取运行中变动的共享模块。
SNAPSHOT = Path(__file__).parents[1] / "Geogram与PaMO切削排斥冻结_20261005_误差分布观察"
sys.path.insert(0, str(SNAPSHOT))
from audit_followup_candidate import sha256, quality_distribution
from audit_cut_delivery import probes
from cut_exclusion import supporting_planes, certify_face_support, face_separators
from cut_side_classifier import ExactCutSide
from exact_alarm_contact import mesh_valid_exact_contacts
from run_constrained_feedback import global_geometry
from run_constrained_batch import RemoteQuality
from run_geometry_study import execute, save, now
from exact_embedding_gate import mesh_valid_full_embedding
from geometry_error_distribution import geometry_error_distribution, cutting_surface_distribution


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--source-batch", type=Path, required=True)
    parser.add_argument("--side-validation", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--kind", choices=["development", "feedback", "continuation", "replay", "unified", "probe"], required=True)
    args = parser.parse_args()
    if args.kind != "unified":
        raise ValueError("严格复用复审仅支持统一完整批次")
    name = {"development": "01-参照自适应排斥开发与审计.json", "feedback": "01-反馈执行与独立审计.json",
            "continuation": "01-输入保护续跑与发布记录.json", "replay": "01-第四刀全量嵌入门控重放.json",
            "unified": "01-统一配置完整父反馈记录.json", "probe": "01-修复源第三刀同输入GPU与审计.json"}[args.kind]
    batch = json.loads((args.batch / name).read_text("utf8"))
    if batch["status"] == "running":
        raise ValueError("批次仍运行，不能做终态保存复审")
    manifest = json.loads((args.prepared / "01-完整范围冻结清单.json").read_text("utf8"))
    if args.kind not in ("development", "replay") and batch["manifest_sha256"] != sha256(args.prepared / "01-完整范围冻结清单.json"):
        raise ValueError("实际反馈输入清单摘要不匹配")
    routes = {r["id"]: r for r in manifest["routes"]}
    args.output.mkdir(exist_ok=False)
    config = dict(line.split("=", 1) for line in (Path(__file__).parents[2] / ".env").read_text("utf8").splitlines()
                  if line and not line.startswith("#"))
    original = getpass.getpass
    try:
        getpass.getpass = lambda _: config["CUDA_SSH_PASSWORD"]
        engine = RemoteQuality(args.output, int(config["CUDA_SSH_PORT"]))
    finally:
        getpass.getpass = original
        del config
    report = {"生成时间": now(), "修改时间及修改内容": "首次生成，独立保存对象复审",
              "文档概述": "重新选择锚点并完整EPECK分类，原面支撑编号保持冻结",
              "索引目录": ["rows", "summary"], "status": "running", "rows": [], "fixed_geometry_acceptance_threshold": None,
              "source_batch_sha256": sha256(args.batch / name), "audit_entry_sha256": sha256(Path(__file__)),
              "dependency_snapshot_manifest_sha256": sha256(SNAPSHOT / "01-执行源码冻结清单.json")}
    record = args.output / "01-保存候选整面与材料侧独立复审.json"
    try:
        if execute(engine.client, ["mkdir", engine.remote])["returncode"]:
            raise ValueError("审计目录已存在")
        validation = json.loads((args.side_validation / "01-精确侧分类器与骨面锚点验证.json").read_text("utf8"))
        executable = validation["environment"]["executable"]
        if execute(engine.client, ["sha256sum", executable])["stdout"].split()[0] != validation["environment"]["executable_sha256"]:
            raise ValueError("精确分类器摘要变化")
        side = ExactCutSide(engine, executable)
        parent_paths = {r["id"]: args.prepared / "inputs" / r["initial_mesh"] for r in routes.values()}
        parents = {r["id"]: r["initial_mesh_sha256"] for r in routes.values()}
        if args.kind in ("continuation", "replay"):
            if len(routes) != 1:
                raise ValueError("续跑审计只支持本批明确的一条路线")
            # 真实续跑从冻结的已发布父状态开始，不把新事件误当初态首刀。
            parents[next(iter(routes))] = (batch["parent_sha256"] if args.kind == "replay"
                                          else batch["inherited_prefix"][-1]["output_sha256"])
        if args.kind == "probe":
            # 同源单刀对照按明确路线及真实父摘要审计，不能当作初态首刀。
            parents[batch["route"]] = batch["parent_sha256"]
        # 单刀重放单独登记，不将它混入旧批次发布分母。
        rows = ([{"event": "e3", "status": "published", "attempt": batch["result"],
                  "parent_sha256": batch["parent_sha256"], "output_sha256": batch["result"]["output_sha256"]}]
                if args.kind == "replay" and batch["accepted"] else batch.get("rows", []))
        if args.kind == "probe" and batch["accepted"]:
            rows = [{"route": batch["route"], "event": batch["event"], "status": "published", "attempt": batch["result"],
                     "parent_sha256": batch["parent_sha256"], "output_sha256": batch["result"]["output_sha256"]}]
        for row in rows:
            if args.kind == "development":
                if not row["details"]["accepted"]:
                    continue
                rid, event, details = row["route"], "e0", row["details"]
                path = args.batch / f"{rid}_candidate.obj"
                parent_matches = True
            elif args.kind == "feedback":
                if row.get("branch") != "candidate" or row["status"] != "published_under_sampled_and_vertex_protocol":
                    continue
                rid, event = row["route"], row["event"]
                details = next(a["cut_exclusion"] for a in row["attempts"] if a["method"] == row["selected_method"])
                path = args.batch / f"{rid}_{event}_candidate_{row['selected_method']}/candidate.obj"
                parent_matches = parents[rid] == row["parent_sha256"]
                parents[rid] = row["output_sha256"]
                parent_paths[rid] = path
            else:
                if row["status"] != "published_geometry_observation":
                    continue
                # 多骨资产的单路线批次必须沿实际路线绑定，不能默认取清单第一骨。
                rid, event = row.get("route", next(iter(routes))), row["event"]
                reuse = row.get("execution_role") == "strict_no_change_reuse"
                identity_passed = True
                if reuse:
                    details = {"cumulative_tool_sha256": [x["tool_sha256"] for x in row["attempt"]["cumulative_tools"]],
                               "cumulative_reference_sha256": row["reference_sha256"]}
                    source_folder = args.batch / f"{rid}_{event}_candidate_input"
                    prior = trimesh.load(parent_paths[rid], force="mesh", process=False)
                    for mesh_name, labels_name in (("source.obj", "labels.json"), ("clean_source.obj", "clean_labels.json")):
                        source = trimesh.load(source_folder / mesh_name, force="mesh", process=False)
                        bits = json.loads((source_folder / labels_name).read_text("utf8"))["operand_bits"]
                        identity_passed = identity_passed and exact_oriented_surface_identity(prior, source, bits)["same"]
                    identity_passed = identity_passed and sha256(parent_paths[rid]) == row["output_sha256"]
                else:
                    details = row["attempt"]["cut_exclusion"]
                    # 支撑证明来自分布排序选中的原提案，不能取原生成器的另一成功对象。
                    outer = details
                    post_area = outer.get("proposal_role") == "certified_raw_seed_projection_then_area_repair"
                    raw_seed = post_area or outer.get("proposal_role") == "raw_seed_projection_after_failed_reference_proposals"
                    if raw_seed:
                        details = dict(outer, cumulative_tool_sha256=outer["cumulative_tool_sha256"],
                            cumulative_reference_sha256=outer["cumulative_reference_sha256"])
                    else:
                        details = dict(outer["proposal_generator"], selected_level=outer["selected_original_attempt_index"],
                            cumulative_tool_sha256=outer["cumulative_tool_sha256"], cumulative_reference_sha256=outer["cumulative_reference_sha256"])
                path = args.batch / f"{rid}_{event}_candidate_boolean/candidate.obj"
                parent_matches = parents[rid] == row["parent_sha256"]
                parents[rid] = row["output_sha256"]
                parent_paths[rid] = path
            mesh = trimesh.load(path, force="mesh", process=False)
            route = routes[rid]
            prefix = set(route["cutting_prefix_ids"][:route["cutting_prefix_ids"].index(event) + 1])
            tool_paths = [args.prepared / "inputs" / t["mesh"] for t in route["prefix_tools"] if t["event_id"] in prefix]
            tools = [trimesh.load(p, force="mesh", process=False) for p in tool_paths]
            planes = [supporting_planes(tool) for tool in tools]
            added_plane_containment_passed = True
            if reuse:
                expanded = []
                for tool, (n, b), saved_certificate in zip(tools, planes, row["attempt"]["cumulative_tools"]):
                    for addition in saved_certificate["support_completion"]["added_planes"]:
                        normal = np.asarray(addition["normal"], np.float64)
                        offset = float(addition["offset_mm"])
                        if normal.shape != (3,) or not np.isfinite(normal).all() or not np.isfinite(offset) or not np.any(normal):
                            raise ValueError("新增支撑方向或偏置无效")
                        # 独立有理数核对工具的所有顶点，不能信任运行记录中的通过布尔值。
                        exact_n = [Fraction(float(x)) for x in normal]
                        contains = all(sum(a * Fraction(float(x)) for a, x in zip(exact_n, point)) <= Fraction(offset)
                                       for point in tool.vertices)
                        added_plane_containment_passed = added_plane_containment_passed and contains
                        if addition["plane_id"] != len(n):
                            raise ValueError("新增支撑编号与实际拼接顺序不符")
                        n, b = np.vstack([n, normal]), np.append(b, offset)
                    expanded.append((n, b))
                planes = expanded
            normals = np.concatenate([n for n, _ in planes])
            offsets = np.concatenate([b for _, b in planes])
            if reuse:
                shift = 0
                selections = []
                for certificate, (n, b) in zip(row["attempt"]["cumulative_tools"], planes):
                    selections.append(np.asarray(certificate["face_support_ids"]) + shift)
                    shift += len(n)
            elif raw_seed:
                if post_area:
                    # 折叠改变面索引，独立重选保存网格的支撑方向，不套用原投影前面号。
                    shift, selections = 0, []
                    for tool, (n, b) in zip(tools, planes):
                        selections.append(face_separators(mesh, tool)[0] + shift)
                        shift += len(n)
                else:
                    selections = details["raw_seed_projection"]["frozen_face_support_ids"]
            else:
                selections = details["attempts"][details["selected_level"]]["exclusion"]["frozen_face_support_ids"]
            faces = [certify_face_support(mesh, normals, offsets, choice) for choice in selections]
            anchors = [side.anchor(mesh, tool, n, b) for tool, (n, b) in zip(tools, planes)]
            reference_folder = args.source_batch / f"{rid}_{event}_reference"
            reference_path = reference_folder / "validated_reference.obj"
            if not reference_path.exists():
                reference_path = reference_folder / "reference.obj"
            reference = trimesh.load(reference_path, force="mesh", process=True, validate=True)
            # 新精确侧分类已经全量审查相同保存对象，以绑定证据取代旧报警数量截断。
            if all(anchor["passed"] for anchor in anchors):
                valid, checks = mesh_valid_full_embedding(mesh, anchors[0]["classification"])
            else:
                valid, checks = mesh_valid_exact_contacts(mesh)
            geometry = global_geometry(mesh, reference)
            if args.kind == "development":
                input_hashes_match = len(tool_paths) == 1 and sha256(tool_paths[0]) == row["tool_sha256"]
                reference_hash_matches = sha256(reference_path) == row["reference_sha256"]
            else:
                input_hashes_match = [sha256(p) for p in tool_paths] == details["cumulative_tool_sha256"]
                reference_hash_matches = sha256(reference_path) == details["cumulative_reference_sha256"]
            expected = row["saved_sha256"] if args.kind == "development" else row["output_sha256"]
            entry = {"route": rid, "event": event, "face_certificates": faces, "anchors": anchors,
                     "parent_hash_matches": parent_matches, "saved_hash_matches": sha256(path) == expected,
                     "input_tool_hashes_match": input_hashes_match, "reference_hash_matches": reference_hash_matches,
                     "checks": checks, "geometry": geometry, "quality": quality_distribution(mesh),
                     "probes": probes(mesh, tools)}
            entry["identity_passed"] = identity_passed
            entry["execution_role"] = row.get("execution_role", "full_GPU_and_correction")
            entry["added_plane_containment_passed"] = added_plane_containment_passed
            entry["passed"] = bool(valid and parent_matches and identity_passed and added_plane_containment_passed
                and input_hashes_match and reference_hash_matches
                and entry["saved_hash_matches"] and all(x["passed"] for x in faces + anchors))
            # 观察版重新采样实际保存对象，两参照分布与切削区域均保留，不以最大值决定几何好坏。
            source_path = args.batch / f"{rid}_{event}_candidate_input/clean_source.obj"
            labels_path = source_path.with_name("clean_labels.json")
            source = trimesh.load(source_path, force="mesh", process=False)
            bits = json.loads(labels_path.read_text("utf8"))["operand_bits"]
            entry["source_hash_matches"] = sha256(source_path) == (row["attempt"]["audited_source_sha256"] if reuse else row["attempt"]["inputs_sha256"]["source.obj"])
            entry["labels_hash_matches"] = sha256(labels_path) == (row["attempt"]["audited_labels_sha256"] if reuse else row["attempt"]["inputs_sha256"]["labels.json"])
            entry["passed"] = entry["passed"] and entry["source_hash_matches"] and entry["labels_hash_matches"]
            entry["geometry_distribution"] = {"maintenance_source": geometry_error_distribution(mesh, source),
                                               "cumulative_reference": geometry_error_distribution(mesh, reference)}
            entry["cutting_surface_distribution"] = cutting_surface_distribution(mesh, source, bits)
            entry["geometry_quality_decision"] = "statistics_only_pending_evaluation"
            report["rows"].append(entry)
            save(record, report)
            print(rid, event, "reaudit", entry["passed"], flush=True)
        report.update(status="completed", finished_beijing=now(), summary={"saved_candidates": len(report["rows"]),
            "passed": sum(r["passed"] for r in report["rows"]), "continuous_target_distance_certified": False})
        save(record, report)
    finally:
        engine.close()


if __name__ == "__main__":
    main()
