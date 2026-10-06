"""复用实际第四刀GPU输出，冻结新全量嵌入门控后重放CPU候选，不改旧拒绝。"""

import argparse
import json
from pathlib import Path
import shutil
from time import perf_counter

import trimesh

from run_reference_cut_feedback import ReferenceCutEngine, audit_full_embedding
from reference_adaptive_exclusion import reference_adaptive_exclusion
from cut_side_classifier import ExactCutSide
from run_geometry_study import execute, save, now
from locality_masks import save_obj_fp64
from audit_followup_candidate import sha256


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--previous", type=Path, required=True)
    parser.add_argument("--side-validation", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    previous_path = args.previous / "01-输入保护续跑与发布记录.json"
    previous = json.loads(previous_path.read_text("utf8"))
    if previous["status"] == "running":
        raise ValueError("前批仍运行")
    third, fourth = previous["rows"]
    if third["status"] != "published" or fourth["event"] != "e3":
        raise ValueError("实际续跑父链不符")
    manifest = json.loads((args.prepared / "01-完整范围冻结清单.json").read_text("utf8"))
    route = manifest["routes"][0]
    rid = route["id"]
    parent = args.previous / f"{rid}_e2_candidate_boolean/candidate.obj"
    if sha256(parent) != third["output_sha256"] or sha256(parent) != fourth["parent_sha256"]:
        raise ValueError("第三刀父状态摘要不符")
    old_folder = args.previous / f"{rid}_e3_candidate_boolean"
    raw = old_folder / "raw_full_candidate.obj"
    if sha256(raw) != fourth["attempt"]["raw_full_output_sha256"]:
        raise ValueError("已执行第四刀GPU对象已改变")
    args.output.mkdir(exist_ok=False)
    ReferenceCutEngine.prepared = args.prepared
    engine = ReferenceCutEngine(args.output, args.port)
    report = {"生成时间": now(), "修改时间及修改内容": "首次生成，先冻结新门控再重放",
              "文档概述": "保留旧拒绝，复用同一真实GPU输出，不新增CUDA调用",
              "索引目录": ["protocol", "result"], "status": "running",
              "snapshot_sha256": sha256(Path(__file__).with_name("01-执行源码冻结清单.json")),
              "protocol": {"full_exact_embedding_gate": True, "geometry_budget_mm": .1, "max_levels": 4,
                           "new_GPU_calls": 0}, "parent_sha256": sha256(parent), "raw_GPU_sha256": sha256(raw)}
    record = args.output / "01-第四刀全量嵌入门控重放.json"
    try:
        if execute(engine.client, ["mkdir", engine.remote])["returncode"]:
            raise ValueError("重放审计目录已存在")
        validation = json.loads((args.side_validation / "01-精确侧分类器与骨面锚点验证.json").read_text("utf8"))
        executable = validation["environment"]["executable"]
        if execute(engine.client, ["sha256sum", executable])["stdout"].split()[0] != validation["environment"]["executable_sha256"]:
            raise ValueError("精确分类器已改变")
        side = ExactCutSide(engine, executable)
        reference_folder = args.output / f"{rid}_e3_reference"
        shutil.copytree(args.previous / reference_folder.name, reference_folder)
        reference_path = reference_folder / "validated_reference.obj"
        if not reference_path.exists():
            reference_path = reference_folder / "reference.obj"
        tool_paths = [args.prepared / "inputs" / t["mesh"] for t in route["prefix_tools"]]
        tools = [trimesh.load(p, force="mesh", process=False) for p in tool_paths]
        reference = trimesh.load(reference_path, force="mesh", process=True, validate=True)
        save(record, report)
        started = perf_counter()
        mesh, details = reference_adaptive_exclusion(trimesh.load(raw, force="mesh", process=False), tools, reference, side.anchor)
        details.update(cumulative_tool_sha256=[sha256(p) for p in tool_paths], cumulative_reference_sha256=sha256(reference_path),
                       CPU_and_remote_audit_ms=(perf_counter() - started) * 1000)
        folder = args.output / f"{rid}_e3_candidate_boolean"
        folder.mkdir()
        path = folder / "candidate.obj"
        save_obj_fp64(mesh, path)
        shutil.copyfile(old_folder / "worker.log", folder / "worker.log")
        row = dict(fourth["attempt"])
        row.update(cut_exclusion=details, output_sha256=sha256(path), gpu_execution_not_repeated=True)
        if details["accepted"]:
            certificate = details["attempts"][details["selected_level"]]["exclusion"]["outside_anchor_certificate"][0]["classification"]
            row["exact_embedding"] = {**certificate, "saved_sha256": sha256(path)}
        input_folder = args.previous / f"{rid}_e3_candidate_input"
        row = audit_full_embedding(input_folder / "clean_source.obj", tool_paths[-1], input_folder / "clean_labels.json", folder, row)
        report.update(status="completed", finished_beijing=now(), result=row,
                      accepted=bool(details["accepted"] and row["status"] == "accepted_sampled"))
        save(record, report)
        print("accepted", report["accepted"], "CPU_ms", details["CPU_and_remote_audit_ms"], flush=True)
    finally:
        engine.close()


if __name__ == "__main__":
    main()
