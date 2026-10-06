"""独立恢复缺失第四刀参照并只执行该刀，前三张观察发布按摘要继承。"""

import argparse
import copy
import json
from pathlib import Path
import shutil

import trimesh
from distribution_observation_engine import DistributionObservationEngine, audit_distribution_observation
from run_cut_exclusion_recovery import exact_recovery
from run_geometry_study import execute, save, now
from audit_followup_candidate import sha256
from geometry_error_distribution import geometry_error_distribution
from run_constrained_feedback import global_geometry
from locality_diagnostic import source_region, verify_labels


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("prepared", "previous", "side-validation", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    old_path = args.previous / "01-统一配置完整父反馈记录.json"
    old = json.loads(old_path.read_text("utf8"))
    if old["status"] != "completed_with_recorded_outcomes" or len(old["rows"]) != 4:
        raise ValueError("要求四事件原完整终态")
    prefix, last = old["rows"][:3], old["rows"][3]
    if any(row["status"] != "published_geometry_observation" for row in prefix) or last["status"] != "independent_reference_missing" or "attempt" in last:
        raise ValueError("只能续跑尚未执行GPU且缺参照的第四刀")
    rid, event = old["selected_route"], last["event"]
    if event != "e3" or last["parent_sha256"] != prefix[-1]["output_sha256"]:
        raise ValueError("第四刀实际父链不同")
    args.output.mkdir(exist_ok=False)
    report = copy.deepcopy(old)
    report.update(生成时间=now(), 修改时间及修改内容="首次生成，原前三刀按摘要继承，仅第四刀独立恢复后续跑",
                  文档概述="原缺参照终态保留，恢复仅使用原初态和工具；旧GPU调用不重做", status="running",
                  inherited_record_sha256=sha256(old_path), inherited_record_path=str(old_path.resolve()),
                  original_interruption=copy.deepcopy(last), new_GPU_calls=0, rows=copy.deepcopy(prefix),
                  continuation_driver_sha256=sha256(Path(__file__)))
    report.pop("summary", None)
    row = copy.deepcopy(last)
    row["status"] = "pending_reference_recovery"
    report["rows"].append(row)
    record = args.output / "01-统一配置完整父反馈记录.json"
    for inherited in prefix:
        stem = rid + "_" + inherited["event"]
        candidate = args.previous / (stem + "_candidate_boolean") / "candidate.obj"
        if sha256(candidate) != inherited["output_sha256"]:
            raise ValueError("继承实际保存网格变化")
        # 仅复制已发布事件真实输入、输出与独立参照，原阶段及分类证据继续绑定旧记录。
        for suffix in ("_candidate_input", "_candidate_boolean", "_reference"):
            shutil.copytree(args.previous / (stem + suffix), args.output / (stem + suffix))
    stem = rid + "_" + event
    shutil.copytree(args.previous / (stem + "_candidate_input"), args.output / (stem + "_candidate_input"))
    source = args.output / (stem + "_candidate_input") / "clean_source.obj"
    labels = source.with_name("clean_labels.json")
    parent_path = args.previous / (rid + "_" + prefix[-1]["event"] + "_candidate_boolean") / "candidate.obj"
    # 原入口只上传父网格而未在输入目录另存parent.obj，核对真实已发布父对象。
    verified_sources = {check["saved_sha256"] for check in last["full_input_checks"] if check.get("embedded_closed")}
    if sha256(parent_path) != last["parent_sha256"] or sha256(source) not in verified_sources:
        raise ValueError("第四刀源的实际父摘要或嵌入证据不同")
    DistributionObservationEngine.prepared, DistributionObservationEngine.side_validation = args.prepared, args.side_validation
    engine = DistributionObservationEngine(args.output, args.port)
    save(record, report)
    try:
        report["continuation_environment"] = engine.setup()
        if report["continuation_environment"]["distribution_code_sha256"] != old["environment"]["distribution_code_sha256"]:
            raise ValueError("续跑核心分布机制与原三刀不同")
        worker = Path(__file__).with_name("run_constrained_worker.py")
        launcher = args.previous / "capacity_launcher.py"
        if sha256(worker) != old["capacity_entry"]["original_worker_sha256"] or sha256(launcher) != old["capacity_entry"]["actual_remote_sha256"]:
            raise ValueError("GPU工作或容量排序入口与原版不同")
        for path, name in ((worker, "original_run_constrained_worker.py"), (launcher, "run_constrained_worker.py")):
            engine.sftp.put(str(path), engine.remote + "/" + name)
            if execute(engine.client, ["sha256sum", engine.remote + "/" + name])["stdout"].split()[0] != sha256(path):
                raise ValueError("实际GPU入口摘要不匹配")
        shutil.copyfile(launcher, args.output / "capacity_launcher.py")
        reference_folder = args.output / (stem + "_reference")
        reference_folder.mkdir()
        recovered, proof = exact_recovery(engine, args.prepared, engine.routes[rid], event, None, reference_folder, False)
        row["independent_reference_recovery"] = proof
        save(record, report)
        if recovered is None:
            row["status"] = "independent_reference_recovery_rejected"
        else:
            tool_info = next(tool for tool in engine.routes[rid]["prefix_tools"] if tool["event_id"] == event)
            tool = args.prepared / "inputs" / tool_info["mesh"]
            if sha256(tool) != last["tool_sha256"]:
                raise ValueError("第四刀工具摘要不同")
            # 使用真实父对象重新核对来源标签，不能仅信任旧行中的成功布尔值。
            maintenance = trimesh.load(source, force="mesh", process=False)
            bits = json.loads(labels.read_text("utf8"))["operand_bits"]
            _, _, seam = source_region(maintenance, bits, allow_shared=True)
            row["continuation_provenance"] = verify_labels(maintenance, bits,
                trimesh.load(parent_path, force="mesh", process=False), trimesh.load(tool, force="mesh", process=False), seam, allow_shared=True)
            if not row["continuation_provenance"]["passed_1e_8_mm_numerical_check"]:
                raise ValueError("续跑来源重新核对失败")
            folder = args.output / (stem + "_candidate_boolean")
            row["status"] = "GPU_and_correction_started"
            report["new_GPU_calls"] = 1
            save(record, report)
            print(event, "GPU_and_correction_started", flush=True)
            attempt = engine.run(source, labels, tool, "boolean", folder)
            attempt = audit_distribution_observation(source, tool, labels, folder, attempt)
            row["attempt"] = attempt
            if attempt["status"] == "accepted_geometry_observation":
                candidate = trimesh.load(folder / "candidate.obj", force="mesh", process=False)
                reference = trimesh.load(reference_folder / "validated_reference.obj", force="mesh", process=True)
                row.update(status="published_geometry_observation", output_sha256=sha256(folder / "candidate.obj"),
                           reference_sha256=sha256(reference_folder / "validated_reference.obj"),
                           cumulative_geometry=global_geometry(candidate, reference),
                           cumulative_distribution=geometry_error_distribution(candidate, reference),
                           geometry_quality_decision="statistics_only_pending_evaluation")
            else:
                row["status"] = "candidate_rejected"
        report.update(status="completed_with_recorded_outcomes", finished_beijing=now(),
                      summary={"published": sum(row["status"] == "published_geometry_observation" for row in report["rows"]),
                               "events": 4, "whole_route_complete": all(row["status"] == "published_geometry_observation" for row in report["rows"])})
        save(record, report)
        print(report["summary"], row["status"], flush=True)
    finally:
        engine.close()


if __name__ == "__main__":
    main()
