"""独立复审工具原点两静态案例，不把旧父绑定误当新连续反馈。"""

import argparse
import getpass
import json
from pathlib import Path
import sys

# 保存审计仍使用原不可变数值模块，不执行编码或任何CUDA方法。
SNAPSHOT = Path(__file__).parents[1] / "Geogram与PaMO切削排斥冻结_20261005_误差分布观察"
sys.path.insert(0, str(SNAPSHOT))
import numpy as np
import trimesh
from audit_followup_candidate import sha256
from cut_exclusion import supporting_planes, certify_face_support
from cut_side_classifier import ExactCutSide
from exact_embedding_gate import mesh_valid_full_embedding
from geometry_error_distribution import geometry_error_distribution, cutting_surface_distribution
from run_constrained_batch import RemoteQuality
from run_geometry_study import execute, save, now


def read(path):
    return json.loads(path.read_text("utf-8-sig"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("prepared", "batch", "source-batch", "reference-batch", "side-validation", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    bp = args.batch / "01-工具原点两源GPU开发验证.json"
    batch = read(bp)
    previous_path = args.source_batch / "01-统一配置完整父反馈记录.json"
    previous = read(previous_path)
    references = read(args.reference_batch / "01-独立累计参照绑定.json")
    mp = args.prepared / "01-完整范围冻结清单.json"
    route = next(r for r in read(mp)["routes"] if r["id"] == previous["selected_route"])
    if (batch["status"] != "completed" or [r["event"] for r in batch["rows"]] != ["e1", "e0"] or
            batch["source_batch_sha256"] != sha256(previous_path) or previous["manifest_sha256"] != sha256(mp) or
            references["manifest_sha256"] != sha256(mp)):
        raise ValueError("静态案例、旧实际父对象或冻结资产不匹配")
    args.output.mkdir(exist_ok=False)
    config = dict(line.split("=", 1) for line in (Path(__file__).parents[2] / ".env").read_text("utf8").splitlines()
                  if line and not line.startswith("#"))
    prompt = getpass.getpass
    try:
        getpass.getpass = lambda _: config["CUDA_SSH_PASSWORD"]
        engine = RemoteQuality(args.output, args.port)
    finally:
        getpass.getpass = prompt
        del config
    report = {"生成时间": now(), "修改时间及修改内容": "首次生成，两静态保存对象独立复审",
              "文档概述": "核对实际CUDA源记录、旧父绑定及保存整面与材料侧；不认证新父反馈",
              "索引目录": ["rows", "summary"], "status": "running", "rows": [], "batch_sha256": sha256(bp)}
    record = args.output / "01-工具原点两保存对象独立复审.json"
    try:
        if execute(engine.client, ["mkdir", engine.remote])["returncode"]:
            raise RuntimeError("独立审计目录无法创建")
        validation = read(args.side_validation / "01-精确侧分类器与骨面锚点验证.json")
        executable = validation["environment"]["executable"]
        if execute(engine.client, ["sha256sum", executable])["stdout"].split()[0] != validation["environment"]["executable_sha256"]:
            raise ValueError("实际材料侧分类器改变")
        side = ExactCutSide(engine, executable)
        for row in batch["rows"]:
            event, attempt = row["event"], row["attempt"]
            old = next(r for r in previous["rows"] if r["event"] == event)
            source_dir = args.source_batch / f"{route['id']}_{event}_candidate_input"
            source, labels = source_dir / "clean_source.obj", source_dir / "clean_labels.json"
            path = args.batch / f"{route['id']}_{event}_candidate_boolean/candidate.obj"
            if (attempt["status"] != "accepted_geometry_observation" or sha256(path) != attempt["output_sha256"] or
                    sha256(source) != row["source_sha256"] or sha256(labels) != row["labels_sha256"] or
                    row["original_parent_sha256"] != old["parent_sha256"] or
                    not attempt["coordinate_pipeline_observations"] or any(
                        d["actual_CUDA_centered_source_zero_or_nonfinite_area"] != 0 for d in attempt["coordinate_pipeline_observations"])):
                raise ValueError("实际源、保存对象、旧父或CUDA非退化证据不匹配")
            prefix = set(route["cutting_prefix_ids"][:route["cutting_prefix_ids"].index(event) + 1])
            tool_paths = [args.prepared / "inputs" / t["mesh"] for t in route["prefix_tools"] if t["event_id"] in prefix]
            details = attempt["cut_exclusion"]
            if [sha256(p) for p in tool_paths] != details["cumulative_tool_sha256"]:
                raise ValueError("累计工具绑定错误")
            tools = [trimesh.load(p, force="mesh", process=False) for p in tool_paths]
            mesh = trimesh.load(path, force="mesh", process=False)
            planes = [supporting_planes(t) for t in tools]
            normals = np.concatenate([n for n, _ in planes])
            offsets = np.concatenate([b for _, b in planes])
            selected = details["proposal_generator"]["attempts"][details["selected_original_attempt_index"]]
            faces = [certify_face_support(mesh, normals, offsets, ids) for ids in selected["exclusion"]["frozen_face_support_ids"]]
            anchors = [side.anchor(mesh, tool, n, b) for tool, (n, b) in zip(tools, planes)]
            valid, metrics = mesh_valid_full_embedding(mesh, anchors[0].get("classification", {}))
            ref = args.reference_batch / f"{route['id']}_{event}_reference/validated_reference.obj"
            if sha256(ref) != details["cumulative_reference_sha256"]:
                raise ValueError("独立累计参照不匹配")
            source_mesh = trimesh.load(source, force="mesh", process=False)
            reference = trimesh.load(ref, force="mesh", process=True, validate=True)
            entry = {"event": event, "saved_sha256": sha256(path), "faces": faces, "anchors": anchors,
                     "checks": metrics, "passed": bool(valid and all(x["passed"] for x in faces + anchors)),
                     "cumulative_distribution": geometry_error_distribution(mesh, reference),
                     "cutting_surface_distribution": cutting_surface_distribution(mesh, source_mesh, read(labels)["operand_bits"])}
            report["rows"].append(entry)
            save(record, report)
            print(event, "static_saved_reaudit", entry["passed"], flush=True)
        report.update(status="completed", finished_beijing=now(), summary={"cases": 2,
            "saved_reaudited_passed": sum(r["passed"] for r in report["rows"]), "new_parent_feedback_certified": False})
        save(record, report)
    finally:
        engine.close()


if __name__ == "__main__":
    main()
