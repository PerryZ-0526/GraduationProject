"""固定真实失败源及父状态，验证修复后的第三刀完整GPU与累计排斥。"""

import argparse
import json
from pathlib import Path
import shutil

import trimesh

from run_reference_cut_feedback import audit_full_embedding
from run_late_reverse_feedback import LateReverseEngine as ReferenceCutEngine
import run_reference_cut_feedback as reference
from local_coverage_exclusion import local_coverage_exclusion
from run_geometry_study import execute, save, now
from audit_followup_candidate import sha256
from run_constrained_feedback import global_geometry


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--previous", type=Path, required=True)
    parser.add_argument("--repair", type=Path, required=True)
    parser.add_argument("--reference-batch", type=Path, required=True)
    parser.add_argument("--side-validation", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    previous = json.loads((args.previous / "01-统一配置完整父反馈记录.json").read_text("utf8"))
    repair_record = args.repair / "01-修复后输入全量门控同源对照.json"
    repair = json.loads(repair_record.read_text("utf8"))
    rid = previous["selected_route"]
    third = next(r for r in previous["rows"] if r["event"] == "e2")
    if third["status"] != "maintenance_input_rejected" or not repair["repair"]["accepted"] or not repair["provenance"]["passed_1e_8_mm_numerical_check"]:
        raise ValueError("本入口需要真实输入拒绝及已绑定的合法修复")
    parent = args.previous / f"{rid}_e1_candidate_boolean/candidate.obj"
    if sha256(parent) != third["parent_sha256"] or sha256(parent) != repair["parent_sha256"]:
        raise ValueError("修复父状态不符")
    ReferenceCutEngine.prepared = args.prepared
    ReferenceCutEngine.side_validation = args.side_validation
    args.output.mkdir(exist_ok=False)
    engine = ReferenceCutEngine(args.output, args.port)
    report = {"生成时间": now(), "修改时间及修改内容": "首次生成，固定旧失败源后启动一次新GPU",
              "文档概述": "只验证第三刀，不声称四刀新版本完整或重跑旧前缀",
              "索引目录": ["environment", "result"], "status": "running", "event": "e2", "route": rid,
              "parent_sha256": sha256(parent), "repair_record_sha256": sha256(repair_record),
              "manifest_sha256": sha256(args.prepared / "01-完整范围冻结清单.json"), "new_GPU_calls": 1}
    record = args.output / "01-修复源第三刀同输入GPU与审计.json"
    try:
        report["environment"] = engine.setup()
        report["actual_method"] = "same_sorted_extension_and_local_coverage_two_rounds_single_repaired_e2"
        report["previous_protocol"] = previous["protocol"]
        report["previous_sorted_extension"] = previous["sorted_extension"]
        # 复用经摘要绑定的同容量入口，只作用于本批隔离目录，不改作者安装。
        launcher = args.previous / "capacity_launcher.py"
        if sha256(launcher) != previous["capacity_entry"]["actual_remote_sha256"] or previous["protocol"]["max_blocks"] != 1 << 26:
            raise ValueError("旧批容量入口不符")
        worker = Path(__file__).with_name("run_constrained_worker.py")
        if sha256(worker) != previous["capacity_entry"]["original_worker_sha256"]:
            raise ValueError("原GPU工作源码已改变")
        engine.sftp.put(str(worker), engine.remote + "/original_run_constrained_worker.py")
        engine.sftp.put(str(launcher), engine.remote + "/run_constrained_worker.py")
        if execute(engine.client, ["sha256sum", engine.remote + "/run_constrained_worker.py"])["stdout"].split()[0] != sha256(launcher):
            raise ValueError("实际容量入口摘要不符")
        route = engine.routes[rid]
        tool = args.prepared / "inputs" / next(t["mesh"] for t in route["prefix_tools"] if t["event_id"] == "e2")
        source, labels = args.repair / "clean_source.obj", args.repair / "clean_labels.json"
        if (sha256(source), sha256(labels), sha256(tool)) != (repair["repaired_sha256"], repair["labels_sha256"], repair["tool_sha256"]):
            raise ValueError("实际修复源、标签或工具摘要不符")
        reference_folder = args.output / f"{rid}_e2_reference"
        shutil.copytree(args.reference_batch / reference_folder.name, reference_folder)
        reference_path = reference_folder / "validated_reference.obj"
        if not reference_path.exists():
            reference_path = reference_folder / "reference.obj"
        save(record, report)
        folder = args.output / f"{rid}_e2_candidate_boolean"
        row = engine.run(source, labels, tool, "boolean", folder)
        row = audit_full_embedding(source, tool, labels, folder, row)
        geometry = global_geometry(trimesh.load(folder / "candidate.obj", force="mesh", process=False),
            trimesh.load(reference_path, force="mesh", process=True, validate=True)) if not row["execution"]["returncode"] else None
        report.update(status="completed", finished_beijing=now(), result=row, cumulative_geometry=geometry,
                      accepted=bool(row["status"] == "accepted_sampled" and geometry["probe_max_mm"] <= .1))
        save(record, report)
        print("same_source_third_accepted", report["accepted"], flush=True)
    finally:
        engine.close()


if __name__ == "__main__":
    reference.reference_adaptive_exclusion = local_coverage_exclusion
    main()
