"""统一容量、输入保护与完整嵌入门槛，从初态执行四刀真实父反馈。"""

import argparse
import json
from pathlib import Path
import shutil

import trimesh

from run_reference_cut_feedback import ReferenceCutEngine, audit_full_embedding
from run_constrained_feedback import PROVENANCE, global_geometry
from run_geometry_study import execute, retrieve, save, now
from audit_followup_candidate import sha256
from audit_cut_embedding import CHECKER
from locality_masks import save_obj_fp64
from locality_cleanup import clean_provenance
from locality_diagnostic import source_region, verify_labels
from fragment_pipeline import repair_input
from study_cut_exclusion import input_valid
from input_full_embedding_audit import audit_input_with_full_embedding


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--reference-batch", type=Path, required=True)
    parser.add_argument("--side-validation", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--route", help="多路线资产中明确指定本次完整开发路线")
    args = parser.parse_args()
    manifest_path = args.prepared / "01-完整范围冻结清单.json"
    manifest = json.loads(manifest_path.read_text("utf8"))
    previous = json.loads((args.reference_batch / "01-反馈执行与独立审计.json").read_text("utf8"))
    if previous["manifest_sha256"] != sha256(manifest_path):
        raise ValueError("本入口要求相同初态与工具的独立累计参照")
    # 多骨开发每次显式选择一条完整路线，结果仍保留该路线所有计划事件。
    routes = [r for r in manifest["routes"] if args.route is None or r["id"] == args.route]
    if len(routes) != 1:
        raise ValueError("必须唯一指定本次完整路线")
    route = routes[0]
    rid = route["id"]
    parent = args.prepared / "inputs" / route["initial_mesh"]
    if sha256(parent) != route["initial_mesh_sha256"]:
        raise ValueError("初态摘要不符")
    args.output.mkdir(exist_ok=False)
    ReferenceCutEngine.prepared = args.prepared
    ReferenceCutEngine.side_validation = args.side_validation
    engine = ReferenceCutEngine(args.output, args.port)
    report = {"生成时间": now(), "修改时间及修改内容": "首次生成，完整路线统一配置先冻结",
              "文档概述": "已见单骨开发，从初态重跑全部事件；旧批次只复用独立累计几何参照",
              "索引目录": ["environment", "rows", "summary"], "status": "running", "rows": [],
              "manifest_sha256": sha256(manifest_path), "reference_batch_sha256": sha256(args.reference_batch / "01-反馈执行与独立审计.json"),
              "snapshot_sha256": sha256(Path(__file__).with_name("01-执行源码冻结清单.json")),
              "protocol": {"max_blocks": 1 << 26, "input_guard": "existing_source_fragment_repair_only_if_invalid",
                           "input_unresolved_alarms_full_embedding_check": True,
                           "full_embedding_gate": True, "geometry_budget_mm": .1, "max_refinement_levels": 4,
                           "GPU_calls_per_event": 1, "fallback": "none", "role": "seen_public_bone_development"},
              "selected_route": rid}
    record = args.output / "01-统一配置完整父反馈记录.json"
    try:
        report["environment"] = engine.setup()
        # 只替换本批隔离目录的入口；作者配置和数学核函数均不修改。
        original_worker = Path(__file__).with_name("run_constrained_worker.py")
        engine.sftp.put(str(original_worker), engine.remote + "/original_run_constrained_worker.py")
        launcher = args.output / "capacity_launcher.py"
        launcher.write_text("\n".join([
            "import hashlib,inspect,json", "from pamo_safe_project import Stage3Config",
            "digest=hashlib.sha256(open(inspect.getfile(Stage3Config),'rb').read()).hexdigest()",
            "assert digest=='df1eb24db57394c32e31f6d67a58cd7ef6c25febc11aff39c5e9503ee82d6390'",
            "original=Stage3Config.__init__", "def larger(self,*args,**kwargs):",
            "    original(self,*args,**kwargs)", "    assert self.max_blocks == 1<<25",
            "    self.max_blocks=1<<26",
            "    print(json.dumps({'original_config_sha256':digest,'max_blocks':self.max_blocks}),flush=True)",
            "Stage3Config.__init__=larger", "import original_run_constrained_worker as worker", "worker.main()"]), encoding="utf8")
        engine.sftp.put(str(launcher), engine.remote + "/run_constrained_worker.py")
        actual = execute(engine.client, ["sha256sum", engine.remote + "/run_constrained_worker.py"])["stdout"].split()[0]
        if actual != sha256(launcher):
            raise ValueError("实际容量入口摘要不符")
        report["capacity_entry"] = {"actual_remote_sha256": actual, "original_worker_sha256": sha256(original_worker)}
        save(record, report)
        for event in route["cutting_prefix_ids"]:
            tool_info = next(t for t in route["prefix_tools"] if t["event_id"] == event)
            tool = args.prepared / "inputs" / tool_info["mesh"]
            if sha256(tool) != tool_info["sha256"]:
                raise ValueError("冻结工具摘要不符")
            folder = args.output / f"{rid}_{event}_candidate_input"
            folder.mkdir()
            row = {"route": rid, "event": event, "parent_sha256": sha256(parent), "tool_sha256": sha256(tool), "status": "pending"}
            report["rows"].append(row)
            save(record, report)
            for path, name in ((parent, "parent.obj"), (tool, "tool.obj")):
                engine.sftp.put(str(path), engine.remote + "/" + name)
                if execute(engine.client, ["sha256sum", engine.remote + "/" + name])["stdout"].split()[0] != sha256(path):
                    raise ValueError("实际布尔父输入或工具摘要不符")
            run = execute(engine.client, [PROVENANCE, engine.remote + "/parent.obj", engine.remote + "/tool.obj",
                engine.remote + "/source.obj", engine.remote + "/labels.json", "--no-simplify"], engine.remote + "/geogram.log")
            row["geogram_execution"] = run
            if run["returncode"]:
                row["status"] = "boolean_rejected"
                break
            for name in ("source.obj", "labels.json"):
                retrieve(engine.client, engine.sftp, engine.remote + "/" + name, folder / name)
            retrieve(engine.client, engine.sftp, engine.remote + "/geogram.log", folder / "geogram.log")
            source = trimesh.load(folder / "source.obj", force="mesh", process=False)
            bits = json.loads((folder / "labels.json").read_text("utf8"))["operand_bits"]
            source, bits, row["cleanup"] = clean_provenance(source, bits, allow_shared=True)
            valid, row["before_input_metrics"] = input_valid(source)
            # 原输入和修复后的候选共用完整门槛，各对象分别绑定摘要；真退化仍交给既有修复。
            check_input = lambda mesh: audit_input_with_full_embedding(engine, folder, mesh, row)
            valid, row["before_full_embedding_metrics"] = check_input(source)
            if not valid:
                source, bits, row["input_repair"] = repair_input(source, bits, audit=check_input, allow_shared=True, allow_small_incident=True)
            valid, row["after_input_metrics"] = check_input(source)
            source_path, labels_path = folder / "clean_source.obj", folder / "clean_labels.json"
            save_obj_fp64(source, source_path)
            save(labels_path, {"operand_bits": bits.tolist()})
            if not valid:
                row["status"] = "maintenance_input_rejected"
                break
            _, _, seam = source_region(source, bits, allow_shared=True)
            row["provenance"] = verify_labels(source, bits, trimesh.load(parent, force="mesh", process=False),
                trimesh.load(tool, force="mesh", process=False), seam, allow_shared=True)
            if not row["provenance"]["passed_1e_8_mm_numerical_check"]:
                row["status"] = "provenance_rejected"
                break
            remote = engine.remote + "/input_for_embedding.obj"
            engine.sftp.put(str(source_path), remote)
            run = execute(engine.client, [CHECKER, remote])
            row["input_exact_embedding"] = json.loads(run["stdout"]) if not run["returncode"] else {"execution": run}
            if not row["input_exact_embedding"].get("embedded_closed"):
                row["status"] = "input_exact_embedding_rejected"
                break
            # 独立累计参照仅由相同初态和工具生成，与本批实际反馈父网格分离。
            reference_folder = args.output / f"{rid}_{event}_reference"
            shutil.copytree(args.reference_batch / reference_folder.name, reference_folder)
            reference_path = reference_folder / "validated_reference.obj"
            if not reference_path.exists():
                reference_path = reference_folder / "reference.obj"
            # 旧累计参照执行失败时保留正常拒绝，不能进入GPU或把缺文件记成算法成功。
            if not reference_path.exists():
                row["status"] = "independent_reference_missing"
                break
            destination = args.output / f"{rid}_{event}_candidate_boolean"
            save(record, report)
            print(event, "GPU_and_correction_started", flush=True)
            attempt = engine.run(source_path, labels_path, tool, "boolean", destination)
            attempt = audit_full_embedding(source_path, tool, labels_path, destination, attempt)
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
        # 每个原计划事件保留状态，不能只用成功事件作分母。
        for event in route["cutting_prefix_ids"]:
            if not any(r["event"] == event for r in report["rows"]):
                report["rows"].append({"route": rid, "event": event, "status": "blocked_by_previous_failure"})
        report.update(status="completed_with_recorded_outcomes", finished_beijing=now(),
            summary={"published": sum(r["status"] == "published" for r in report["rows"]),
                     "events": len(route["cutting_prefix_ids"]), "whole_route_complete": all(r["status"] == "published" for r in report["rows"])})
        save(record, report)
        print(report["summary"], flush=True)
    finally:
        engine.close()


if __name__ == "__main__":
    main()
