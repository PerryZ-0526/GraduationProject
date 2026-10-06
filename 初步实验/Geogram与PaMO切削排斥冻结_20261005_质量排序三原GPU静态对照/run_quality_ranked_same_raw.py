"""三张已保存原GPU输出的质量排序静态对照，不重跑GPU或声称新父反馈。"""

import argparse
import getpass
import hashlib
import json
import os
from pathlib import Path
import sys


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("snapshot", "batch", "prepared", "side-validation", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    manifest = args.snapshot / "01-执行源码冻结清单.json"
    for item in json.loads(manifest.read_text("utf8")):
        if sha(args.snapshot / item["file"]) != item["sha256"]:
            raise ValueError("固定提案数值依赖改变")
    sys.path.insert(0, str(args.snapshot.resolve()))
    import numpy as np
    import trimesh
    from quality_ranked_exclusion import quality_ranked_exclusion
    from cut_side_classifier import ExactCutSide
    from cut_exclusion import supporting_planes, certify_face_support
    from exact_embedding_gate import mesh_valid_full_embedding
    from geometry_error_distribution import geometry_error_distribution, cutting_surface_distribution
    from audit_followup_candidate import quality_distribution
    from audit_cut_delivery import probes
    from locality_masks import save_obj_fp64
    from run_constrained_batch import RemoteQuality
    from run_geometry_study import execute, save, now
    bp = args.batch / "01-统一配置完整父反馈记录.json"
    batch = json.loads(bp.read_text("utf8"))
    prepared_manifest = args.prepared / "01-完整范围冻结清单.json"
    prepared = json.loads(prepared_manifest.read_text("utf8"))
    route = next(r for r in prepared["routes"] if r["id"] == batch["selected_route"])
    if batch["status"] != "completed_with_recorded_outcomes" or batch["summary"]["published"] != 3 or batch["manifest_sha256"] != sha(prepared_manifest):
        raise ValueError("静态对照要求同一三刀完整开发终态")
    args.output.mkdir(exist_ok=False)
    record = args.output / "01-三张原GPU同源质量排序静态对照.json"
    report = {"生成时间": now(), "修改时间及修改内容": "首次生成，三张保存原GPU固定提案质量排序",
              "文档概述": "父源沿用旧几何排序链，逐张静态对照，不是质量排序新连续反馈",
              "索引目录": ["rows"], "status": "running", "rows": [], "new_GPU_calls": 0,
              "new_parent_feedback": False, "batch_sha256": sha(bp), "snapshot_sha256": sha(manifest),
              "quality_ranked_source_sha256": sha(Path(__file__).with_name("quality_ranked_exclusion.py"))}
    save(record, report)
    cfg = dict(line.split("=", 1) for line in (args.snapshot.resolve().parents[1] / ".env").read_text("utf8").splitlines()
               if line and not line.startswith("#"))
    prompt = getpass.getpass
    os.environ["GPU_SSH_HOST"] = "connect.westb.seetacloud.com"
    try:
        getpass.getpass = lambda _: cfg["CUDA_SSH_PASSWORD"]
        engine = RemoteQuality(args.output, 51667)
    finally:
        getpass.getpass = prompt
        del cfg
    try:
        if execute(engine.client, ["mkdir", engine.remote])["returncode"]:
            raise ValueError("静态审计隔离目录无法创建")
        validation = json.loads((args.side_validation / "01-精确侧分类器与骨面锚点验证.json").read_text("utf8"))
        executable = validation["environment"]["executable"]
        if execute(engine.client, ["sha256sum", executable])["stdout"].split()[0] != validation["environment"]["executable_sha256"]:
            raise ValueError("精确材料侧分类器改变")
        side = ExactCutSide(engine, executable)
        for index, previous in enumerate(batch["rows"]):
            event = previous["event"]
            stem = route["id"] + "_" + event
            folder = args.batch / (stem + "_candidate_boolean")
            raw_path, old_path = folder / "raw_full_candidate.obj", folder / "candidate.obj"
            source_path = args.batch / (stem + "_candidate_input/clean_source.obj")
            labels_path = source_path.with_name("clean_labels.json")
            reference_path = args.batch / (stem + "_reference/validated_reference.obj")
            if (sha(raw_path) != previous["attempt"]["raw_full_output_sha256"] or sha(old_path) != previous["output_sha256"] or
                    sha(source_path) != previous["attempt"]["inputs_sha256"]["source.obj"] or
                    sha(labels_path) != previous["attempt"]["inputs_sha256"]["labels.json"] or sha(reference_path) != previous["reference_sha256"]):
                raise ValueError("静态同源对照对象摘要不一致")
            tool_items = [t for t in route["prefix_tools"] if t["event_id"] in route["cutting_prefix_ids"][:index + 1]]
            tools = []
            for item in tool_items:
                path = args.prepared / "inputs" / item["mesh"]
                if sha(path) != item["sha256"]:
                    raise ValueError("静态累计工具摘要改变")
                tools.append(trimesh.load(path, force="mesh", process=False))
            source = trimesh.load(source_path, force="mesh", process=False)
            reference = trimesh.load(reference_path, force="mesh", process=True, validate=True)
            bits = json.loads(labels_path.read_text("utf8"))["operand_bits"]
            mesh, details = quality_ranked_exclusion(trimesh.load(raw_path, force="mesh", process=False), tools, reference, source, bits, side.anchor)
            row = {"event": event, "raw_sha256": sha(raw_path), "old_saved_sha256": sha(old_path),
                   "source_sha256": sha(source_path), "labels_sha256": sha(labels_path), "reference_sha256": sha(reference_path),
                   "details": details, "actual_old_parent_sha256": previous["parent_sha256"], "passed": False}
            report["rows"].append(row)
            if details["accepted"]:
                destination = args.output / event
                destination.mkdir()
                saved = destination / "01-质量排序静态候选.obj"
                save_obj_fp64(mesh, saved)
                loaded = trimesh.load(saved, force="mesh", process=False)
                planes = [supporting_planes(tool) for tool in tools]
                normals, offsets = np.concatenate([p[0] for p in planes]), np.concatenate([p[1] for p in planes])
                attempt = details["proposal_generator"]["attempts"][details["selected_original_attempt_index"]]["exclusion"]
                faces = [certify_face_support(loaded, normals, offsets, choice) for choice in attempt["frozen_face_support_ids"]]
                anchors = [side.anchor(loaded, tool, n, b) for tool, (n, b) in zip(tools, planes)]
                valid, metrics = mesh_valid_full_embedding(loaded, anchors[0]["classification"])
                topology = loaded.euler_number == source.euler_number and len(loaded.split(only_watertight=False)) == len(source.split(only_watertight=False))
                row.update(saved_sha256=sha(saved), face_certificates=faces, anchors=anchors, output_metrics=metrics,
                           passed=bool(valid and topology and all(r["passed"] for r in faces + anchors)),
                           cumulative_distribution=geometry_error_distribution(loaded, reference),
                           cutting_surface_distribution=cutting_surface_distribution(loaded, source, bits),
                           quality=quality_distribution(loaded), finite_intrusion_witnesses=probes(loaded, tools),
                           old_geometry_ranked_quality=quality_distribution(trimesh.load(old_path, force="mesh", process=False)))
            save(record, report)
            print(event, "static_quality_ranked", row["passed"], flush=True)
        report.update(status="completed", finished_beijing=now(), summary={"events": 3, "passed": sum(r["passed"] for r in report["rows"]),
                                                                          "new_GPU_calls": 0, "new_parent_feedback": False})
        save(record, report)
    finally:
        engine.sftp.close()
        engine.client.close()


if __name__ == "__main__":
    main()
