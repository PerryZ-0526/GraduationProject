"""重新加载六张偏移消融维护输出，独立核对冻结整面支撑和精确材料侧。"""

import argparse
import json
from pathlib import Path

import numpy as np
import trimesh
from run_reference_cut_feedback import ReferenceCutEngine
from audit_followup_candidate import sha256
from cut_exclusion import supporting_planes, certify_face_support
from cut_side_classifier import ExactCutSide
from exact_embedding_gate import mesh_valid_full_embedding
from run_geometry_study import execute, save, now


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("batch", "previous", "prepared", "side-validation", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--probes", type=Path, nargs=3, required=True)
    args = parser.parse_args()
    path = args.batch / "01-三档偏移六输出同版维护与保存复审.json"
    batch = json.loads(path.read_text("utf8"))
    old_path = args.previous / "01-统一配置完整父反馈记录.json"
    old = json.loads(old_path.read_text("utf8"))
    manifest_path = args.prepared / "01-完整范围冻结清单.json"
    manifest = json.loads(manifest_path.read_text("utf8"))
    if batch["status"] != "completed" or len(batch["rows"]) != 6 or sha256(old_path) != batch["bindings"]["previous_sha256"] or sha256(manifest_path) != old["manifest_sha256"]:
        raise ValueError("要求同一父状态与清单的六输出维护终态")
    origins = {}
    for root in args.probes:
        probe_path = root / "01-简化邻接顺序同输入完整对照.json"
        probe = json.loads(probe_path.read_text("utf8"))
        if probe["status"] != "completed" or probe["previous_record_sha256"] != sha256(old_path) or probe["selected_event"] != "e1":
            raise ValueError("GPU来源记录不匹配同一实际父状态")
        for index, gpu in enumerate(probe["rows"], 1):
            raw_path = root / f"同输入GPU第{index}次" / "candidate.obj"
            if gpu["execution"]["returncode"] or sha256(raw_path) != gpu["output_sha256"]:
                raise ValueError("实际原GPU对象摘要改变")
            origins[probe["offset_factor"], index] = (sha256(probe_path), sha256(raw_path))
    if set(origins) != {(factor, index) for factor in (0.9, 0.45, 0.0) for index in (1, 2)}:
        raise ValueError("三档六输出GPU来源分母不完整")
    if {(row["offset_factor"], row["repeat"]) for row in batch["rows"]} != set(origins):
        raise ValueError("维护六对象编号有重复或缺失")
    route = next(row for row in manifest["routes"] if row["id"] == old["selected_route"])
    event = next(row for row in old["rows"] if row["event"] == "e1")
    parent = next(row for row in old["rows"] if row["event"] == "e0")
    if event["parent_sha256"] != parent["output_sha256"]:
        raise ValueError("原第二刀真实父摘要不匹配")
    stem = route["id"] + "_e1"
    source_path = args.previous / (stem + "_candidate_input") / "clean_source.obj"
    labels_path = source_path.with_name("clean_labels.json")
    reference_path = args.previous / (stem + "_reference") / "validated_reference.obj"
    if not reference_path.exists():
        reference_path = reference_path.with_name("reference.obj")
    for file, key in ((source_path, "source_sha256"), (labels_path, "labels_sha256"), (reference_path, "reference_sha256")):
        if sha256(file) != batch["bindings"][key]:
            raise ValueError("实际维护绑定对象摘要改变")
    maintenance = trimesh.load(source_path, force="mesh", process=False)
    entries = [entry for entry in route["prefix_tools"] if entry["event_id"] in ("e0", "e1")]
    tool_paths = [args.prepared / "inputs" / entry["mesh"] for entry in entries]
    tool_hashes = [sha256(file) for file in tool_paths]
    if tool_hashes != event["attempt"]["cut_exclusion"]["cumulative_tool_sha256"] or any(digest != entry["sha256"] for digest, entry in zip(tool_hashes, entries)):
        raise ValueError("两个累计工具与原执行绑定不匹配")
    tools = [trimesh.load(file, force="mesh", process=False) for file in tool_paths]
    planes = [supporting_planes(tool) for tool in tools]
    normals = np.concatenate([n for n, _ in planes])
    offsets = np.concatenate([b for _, b in planes])
    args.output.mkdir(exist_ok=False)
    # 继承连接器在构造时读取清单，独立复审也必须先绑定相同的冻结输入。
    ReferenceCutEngine.prepared = args.prepared
    engine = ReferenceCutEngine(args.output, args.port)
    report = {"生成时间": now(), "修改时间及修改内容": "首次生成，六保存输出整面材料侧独立复审",
              "文档概述": "同一第二刀父状态的六静态对象，不假装六刀连续反馈；不设几何覆盖率接受门槛",
              "索引目录": ["rows", "summary"], "status": "running", "new_GPU_calls": 0,
              "batch_sha256": sha256(path), "entry_sha256": sha256(Path(__file__)), "tool_sha256": tool_hashes, "rows": []}
    record = args.output / "01-六张保存输出整面与材料侧独立复审.json"
    save(record, report)
    try:
        if execute(engine.client, ["mkdir", engine.remote])["returncode"]:
            raise ValueError("独立审计目录已存在")
        validation = json.loads((args.side_validation / "01-精确侧分类器与骨面锚点验证.json").read_text("utf8"))
        executable = validation["environment"]["executable"]
        if execute(engine.client, ["sha256sum", executable])["stdout"].split()[0] != validation["environment"]["executable_sha256"]:
            raise ValueError("已验证精确分类器改变")
        side = ExactCutSide(engine, executable)
        for row in batch["rows"]:
            if (row["probe_record_sha256"], row["raw_sha256"]) != origins[row["offset_factor"], row["repeat"]]:
                raise ValueError("维护输出未绑定对应真实GPU来源")
            item = {"offset_factor": row["offset_factor"], "repeat": row["repeat"], "originally_accepted": row["accepted_geometry_observation"]}
            report["rows"].append(item)
            if not row["accepted_geometry_observation"]:
                item.update(status="recorded_rejection_no_observation", passed=False)
                save(record, report)
                continue
            candidate_path = args.batch / f"偏移{row['offset_factor']}_重复{row['repeat']}" / "candidate.obj"
            if sha256(candidate_path) != row["saved_sha256"]:
                raise ValueError("实际保存候选摘要改变")
            mesh = trimesh.load(candidate_path, force="mesh", process=False)
            details = row["result"]
            selected = details["proposal_generator"]["attempts"][details["selected_original_attempt_index"]]
            selections = selected["exclusion"]["frozen_face_support_ids"]
            faces = [certify_face_support(mesh, normals, offsets, choice) for choice in selections]
            anchors = [side.anchor(mesh, tool, n, b) for tool, (n, b) in zip(tools, planes)]
            valid, checks = mesh_valid_full_embedding(mesh, anchors[0]["classification"])
            same_topology = mesh.euler_number == maintenance.euler_number and len(mesh.split(only_watertight=False)) == len(maintenance.split(only_watertight=False))
            # 重新选择材料锚点并绑定当前保存对象，不以旧成功标志或几何比例代替证书。
            hashes_match = all(anchor["classification"].get("saved_mesh_sha256") == row["saved_sha256"] for anchor in anchors)
            item.update(status="reaudited", saved_sha256=sha256(candidate_path), face_certificates=faces, anchors=anchors,
                checks=checks, same_topology_as_source=same_topology, classification_hashes_match=hashes_match,
                passed=bool(valid and same_topology and hashes_match and all(value["passed"] for value in faces + anchors)))
            save(record, report)
            print(row["offset_factor"], row["repeat"], item["passed"], flush=True)
        report.update(status="completed", finished_beijing=now(), summary={"planned": 6,
            "originally_accepted": sum(row["originally_accepted"] for row in report["rows"]),
            "saved_reaudited_passed": sum(row["passed"] for row in report["rows"])})
        save(record, report)
    finally:
        engine.close()


if __name__ == "__main__":
    main()
