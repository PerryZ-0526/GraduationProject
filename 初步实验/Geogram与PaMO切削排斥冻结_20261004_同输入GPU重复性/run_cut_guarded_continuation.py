"""从已复审第二刀父状态续跑，加入来源碎片输入保护，不重跑已发布前缀。"""

import argparse
import json
from pathlib import Path
import shutil

import trimesh

import run_cut_exclusion_feedback as first
from run_reference_cut_feedback import ReferenceCutEngine
from run_cut_exclusion_continuation import audit
from run_constrained_feedback import PROVENANCE, global_geometry
from run_geometry_study import execute, retrieve, save, now
from audit_followup_candidate import sha256
from audit_cut_embedding import CHECKER
from locality_masks import save_obj_fp64
from locality_cleanup import clean_provenance
from locality_diagnostic import source_region, verify_labels
from fragment_pipeline import repair_input
from study_cut_exclusion import input_valid
from exact_alarm_contact import mesh_valid_exact_contacts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--previous", type=Path, required=True)
    parser.add_argument("--side-validation", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    previous_path = args.previous / "01-反馈执行与独立审计.json"
    previous = json.loads(previous_path.read_text("utf8"))
    published = [r for r in previous["rows"] if r.get("branch") == "candidate"
                 and r["status"] == "published_under_sampled_and_vertex_protocol"]
    if [r["event"] for r in published] != ["e0", "e1"]:
        raise ValueError("续跑前缀不是已复审的前两刀")
    args.output.mkdir(exist_ok=False)
    manifest = json.loads((args.prepared / "01-完整范围冻结清单.json").read_text("utf8"))
    route = manifest["routes"][0]
    rid = route["id"]
    parent = args.previous / f"{rid}_e1_candidate_boolean/candidate.obj"
    if sha256(parent) != published[-1]["output_sha256"]:
        raise ValueError("实际续跑父状态已改变")
    ReferenceCutEngine.prepared = args.prepared
    ReferenceCutEngine.side_validation = args.side_validation
    engine = ReferenceCutEngine(args.output, args.port)
    first.mesh_valid = mesh_valid_exact_contacts
    report = {"生成时间": now(), "修改时间及修改内容": "首次生成，真实父状态开发续跑",
              "文档概述": "输入保护为新版本，旧两刀前缀独立登记，不改写旧拒绝",
              "索引目录": ["inherited_prefix", "rows", "summary"], "status": "running", "rows": [],
              "previous_batch_sha256": sha256(previous_path), "manifest_sha256": sha256(args.prepared / "01-完整范围冻结清单.json"),
              "inherited_prefix": [{"event": r["event"], "output_sha256": r["output_sha256"]} for r in published]}
    record = args.output / "01-输入保护续跑与发布记录.json"
    try:
        report["environment"] = engine.setup()
        save(record, report)
        for event in route["cutting_prefix_ids"][2:]:
            tool = args.prepared / "inputs" / next(t["mesh"] for t in route["prefix_tools"] if t["event_id"] == event)
            folder = args.output / f"{rid}_{event}_candidate_input"
            folder.mkdir()
            row = {"event": event, "parent_sha256": sha256(parent), "tool_sha256": sha256(tool), "status": "pending"}
            report["rows"].append(row)
            if event == "e2":
                # 第三刀旧布尔输入已经保存，绑定同一父和工具后原样复用，不重新生成三角化。
                old_row = next(r for r in previous["rows"] if r.get("branch") == "candidate" and r["event"] == event)
                if (old_row["parent_sha256"], old_row["tool_sha256"]) != (sha256(parent), sha256(tool)):
                    raise ValueError("保存第三刀输入与续跑父工具不一致")
                for name in ("source.obj", "labels.json"):
                    shutil.copyfile(args.previous / f"{rid}_{event}_candidate_input" / name, folder / name)
            else:
                for path, name in ((parent, "parent.obj"), (tool, "tool.obj")):
                    engine.sftp.put(str(path), engine.remote + "/" + name)
                run = execute(engine.client, [PROVENANCE, engine.remote + "/parent.obj", engine.remote + "/tool.obj",
                    engine.remote + "/source.obj", engine.remote + "/labels.json", "--no-simplify"], engine.remote + "/geogram.log")
                row["geogram_execution"] = run
                if run["returncode"]:
                    row["status"] = "boolean_rejected"
                    break
                for name in ("source.obj", "labels.json"):
                    retrieve(engine.client, engine.sftp, engine.remote + "/" + name, folder / name)
            source = trimesh.load(folder / "source.obj", force="mesh", process=False)
            bits = json.loads((folder / "labels.json").read_text("utf8"))["operand_bits"]
            source, bits, cleanup = clean_provenance(source, bits, allow_shared=True)
            valid, metrics = input_valid(source)
            row.update(cleanup=cleanup, before_input_metrics=metrics)
            if not valid:
                source, bits, repair = repair_input(source, bits, audit=input_valid, allow_shared=True, allow_small_incident=True)
                row["input_repair"] = repair
            valid, metrics = input_valid(source)
            row["after_input_metrics"] = metrics
            source_path, labels_path = folder / "clean_source.obj", folder / "clean_labels.json"
            save_obj_fp64(source, source_path)
            save(labels_path, {"operand_bits": bits.tolist()})
            if not valid:
                row["status"] = "maintenance_input_rejected"
                break
            _, _, seam = source_region(source, bits, allow_shared=True)
            provenance = verify_labels(source, bits, trimesh.load(parent, force="mesh", process=False),
                                       trimesh.load(tool, force="mesh", process=False), seam, allow_shared=True)
            row["provenance"] = provenance
            if not provenance["passed_1e_8_mm_numerical_check"]:
                row["status"] = "provenance_rejected"
                break
            remote = engine.remote + "/input_for_embedding.obj"
            engine.sftp.put(str(source_path), remote)
            run = execute(engine.client, [CHECKER, remote])
            row["input_exact_embedding"] = json.loads(run["stdout"]) if not run["returncode"] else {"execution": run}
            if not row["input_exact_embedding"].get("embedded_closed"):
                row["status"] = "input_exact_embedding_rejected"
                break
            reference_folder = args.output / f"{rid}_{event}_reference"
            shutil.copytree(args.previous / reference_folder.name, reference_folder)
            reference_path = reference_folder / "validated_reference.obj"
            if not reference_path.exists():
                reference_path = reference_folder / "reference.obj"
            destination = args.output / f"{rid}_{event}_candidate_boolean"
            attempt = engine.run(source_path, labels_path, tool, "boolean", destination)
            attempt = audit(source_path, tool, labels_path, destination, attempt)
            row["attempt"] = attempt
            if attempt["status"] != "accepted_sampled":
                row["status"] = "candidate_rejected"
                break
            candidate_path = destination / "candidate.obj"
            candidate = trimesh.load(candidate_path, force="mesh", process=False)
            reference = trimesh.load(reference_path, force="mesh", process=True, validate=True)
            row["cumulative_geometry"] = global_geometry(candidate, reference)
            if row["cumulative_geometry"]["probe_max_mm"] > .1:
                row["status"] = "cumulative_geometry_rejected"
                break
            row.update(status="published", output_sha256=sha256(candidate_path), reference_sha256=sha256(reference_path))
            parent = candidate_path
            save(record, report)
            print(event, "published", flush=True)
        # 未执行事件必须明确保留阻断记录，继承前缀与新执行分母分别统计。
        for event in route["cutting_prefix_ids"][2:]:
            if not any(r["event"] == event for r in report["rows"]):
                report["rows"].append({"event": event, "status": "blocked_by_previous_failure"})
        report.update(status="completed_with_recorded_outcomes", finished_beijing=now(),
                      summary={"inherited_published": 2, "new_published": sum(r["status"] == "published" for r in report["rows"]),
                               "remaining_events": 2, "whole_route_complete": all(r["status"] == "published" for r in report["rows"])})
        save(record, report)
        print(report["summary"], flush=True)
    finally:
        engine.close()


if __name__ == "__main__":
    main()
