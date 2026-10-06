"""独立重加载参照自适应候选，复核冻结整面支撑和精确材料外锚点。"""

import argparse
import getpass
import json
from pathlib import Path
import sys

import numpy as np
import trimesh

# 审计与开发版本共用不可变数值协议，不能读取运行中变动的共享模块。
SNAPSHOT = Path(__file__).parents[1] / "Geogram与PaMO切削排斥冻结_20261004_参照自适应"
sys.path.insert(0, str(SNAPSHOT))
from audit_followup_candidate import sha256, quality_distribution
from audit_cut_delivery import probes
from cut_exclusion import supporting_planes, certify_face_support
from cut_side_classifier import ExactCutSide
from exact_alarm_contact import mesh_valid_exact_contacts
from run_constrained_feedback import global_geometry
from run_constrained_batch import RemoteQuality
from run_geometry_study import execute, save, now
from exact_embedding_gate import mesh_valid_full_embedding


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--source-batch", type=Path, required=True)
    parser.add_argument("--side-validation", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--kind", choices=["development", "feedback", "continuation", "replay", "unified"], required=True)
    args = parser.parse_args()
    name = {"development": "01-参照自适应排斥开发与审计.json", "feedback": "01-反馈执行与独立审计.json",
            "continuation": "01-输入保护续跑与发布记录.json", "replay": "01-第四刀全量嵌入门控重放.json",
            "unified": "01-统一配置完整父反馈记录.json"}[args.kind]
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
              "索引目录": ["rows", "summary"], "status": "running", "rows": [],
              "source_batch_sha256": sha256(args.batch / name)}
    record = args.output / "01-保存候选整面与材料侧独立复审.json"
    try:
        if execute(engine.client, ["mkdir", engine.remote])["returncode"]:
            raise ValueError("审计目录已存在")
        validation = json.loads((args.side_validation / "01-精确侧分类器与骨面锚点验证.json").read_text("utf8"))
        executable = validation["environment"]["executable"]
        if execute(engine.client, ["sha256sum", executable])["stdout"].split()[0] != validation["environment"]["executable_sha256"]:
            raise ValueError("精确分类器摘要变化")
        side = ExactCutSide(engine, executable)
        parents = {r["id"]: r["initial_mesh_sha256"] for r in routes.values()}
        if args.kind in ("continuation", "replay"):
            if len(routes) != 1:
                raise ValueError("续跑审计只支持本批明确的一条路线")
            # 真实续跑从冻结的已发布父状态开始，不把新事件误当初态首刀。
            parents[next(iter(routes))] = (batch["parent_sha256"] if args.kind == "replay"
                                          else batch["inherited_prefix"][-1]["output_sha256"])
        # 单刀重放单独登记，不将它混入旧批次发布分母。
        rows = ([{"event": "e3", "status": "published", "attempt": batch["result"],
                  "parent_sha256": batch["parent_sha256"], "output_sha256": batch["result"]["output_sha256"]}]
                if args.kind == "replay" and batch["accepted"] else batch.get("rows", []))
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
            else:
                if row["status"] != "published":
                    continue
                # 多骨资产的单路线批次必须沿实际路线绑定，不能默认取清单第一骨。
                rid, event = row.get("route", next(iter(routes))), row["event"]
                details = row["attempt"]["cut_exclusion"]
                path = args.batch / f"{rid}_{event}_candidate_boolean/candidate.obj"
                parent_matches = parents[rid] == row["parent_sha256"]
                parents[rid] = row["output_sha256"]
            mesh = trimesh.load(path, force="mesh", process=False)
            route = routes[rid]
            prefix = set(route["cutting_prefix_ids"][:route["cutting_prefix_ids"].index(event) + 1])
            tool_paths = [args.prepared / "inputs" / t["mesh"] for t in route["prefix_tools"] if t["event_id"] in prefix]
            tools = [trimesh.load(p, force="mesh", process=False) for p in tool_paths]
            planes = [supporting_planes(tool) for tool in tools]
            normals = np.concatenate([n for n, _ in planes])
            offsets = np.concatenate([b for _, b in planes])
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
            entry["passed"] = bool(valid and geometry["probe_max_mm"] <= .1 and parent_matches
                and input_hashes_match and reference_hash_matches
                and entry["saved_hash_matches"] and all(x["passed"] for x in faces + anchors))
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
