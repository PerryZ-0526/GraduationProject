"""复用真实第四刀原始GPU对象，只执行双参照后处理和完整保存审计。"""

import argparse
import json
from pathlib import Path
from time import perf_counter

import trimesh

from run_reference_cut_feedback import ReferenceCutEngine
from run_geometry_study import execute, save, now
from audit_followup_candidate import sha256
from audit_cut_embedding import CHECKER
from locality_masks import save_obj_fp64
from exact_embedding_gate import mesh_valid_full_embedding
from dual_reference_coverage_exclusion import dual_reference_coverage_exclusion, dual_reference_geometry


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--previous", type=Path, required=True)
    parser.add_argument("--side-validation", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    old_path = args.previous / "01-统一配置完整父反馈记录.json"
    old = json.loads(old_path.read_text("utf8"))
    row = next(r for r in old["rows"] if r["event"] == "e3")
    if old["status"] == "running" or row["status"] != "candidate_rejected":
        raise ValueError("需要已终态的第四刀真实拒绝")
    rid = old["selected_route"]
    folder = args.previous / f"{rid}_e3_candidate_boolean"
    source = args.previous / f"{rid}_e3_candidate_input/clean_source.obj"
    raw = folder / "raw_full_candidate.obj"
    cumulative = args.previous / f"{rid}_e3_reference/validated_reference.obj"
    if not cumulative.exists():
        cumulative = cumulative.with_name("reference.obj")
    expected = row["attempt"]
    bindings = {"raw": (raw, expected["raw_full_output_sha256"]),
                "maintenance_source": (source, expected["inputs_sha256"]["source.obj"]),
                "cumulative_reference": (cumulative, expected["cut_exclusion"]["cumulative_reference_sha256"]),
                "old_candidate": (folder / "candidate.obj", expected["output_sha256"])}
    if any(sha256(path) != digest for path, digest in bindings.values()):
        raise ValueError("实际保存输入或旧输出摘要不符")
    args.output.mkdir(exist_ok=False)
    ReferenceCutEngine.prepared = args.prepared
    ReferenceCutEngine.side_validation = args.side_validation
    engine = ReferenceCutEngine(args.output, args.port)
    report = {"生成时间": now(), "修改时间及修改内容": "首次生成，同输入后处理先冻结",
              "文档概述": "只验证旧第四刀，不是完整新父链或新GPU复跑",
              "索引目录": ["bindings", "old_geometry", "result"], "status": "running",
              "new_GPU_calls": 0, "previous_record_sha256": sha256(old_path),
              "bindings": {k: {"path": str(p.resolve()), "sha256": h} for k, (p, h) in bindings.items()},
              "mechanism_sha256": sha256(Path(__file__).with_name("dual_reference_coverage_exclusion.py"))}
    record = args.output / "01-第四刀双参照同输入恢复与审计.json"
    save(record, report)
    try:
        report["environment"] = engine.setup()
        report["protocol"] = {"new_GPU_calls": 0, "coverage_rounds": 2,
            "projection_step_fractions": [1., .5, .25], "maximum_coverage_proposals": 6,
            "dual_reference_stop_required": True, "distance_budget_mm": .1}
        reference = trimesh.load(cumulative, force="mesh", process=True, validate=True)
        maintenance = trimesh.load(source, force="mesh", process=False)
        report["old_geometry"] = dual_reference_geometry(
            trimesh.load(folder / "candidate.obj", force="mesh", process=False), reference, maintenance)
        route = engine.routes[rid]
        tools = []
        report["tool_sha256"] = []
        # 固定完整前缀的四把工具，不能只约束本刀。
        prefix = set(route["cutting_prefix_ids"][:route["cutting_prefix_ids"].index("e3") + 1])
        for tool in route["prefix_tools"]:
            if tool["event_id"] not in prefix:
                continue
            path = args.prepared / "inputs" / tool["mesh"]
            if sha256(path) != tool["sha256"]:
                raise ValueError("实际累计工具摘要不符")
            tools.append(trimesh.load(path, force="mesh", process=False))
            report["tool_sha256"].append(sha256(path))
        if report["tool_sha256"] != expected["cut_exclusion"]["cumulative_tool_sha256"]:
            raise ValueError("同输入累计工具前缀不一致")
        save(record, report)
        started = perf_counter()
        candidate, details = dual_reference_coverage_exclusion(
            trimesh.load(raw, force="mesh", process=False), tools, reference, maintenance, engine.side.anchor)
        report["postprocessing_ms"] = (perf_counter() - started) * 1000
        path = args.output / "candidate.obj"
        save_obj_fp64(candidate, path)
        remote = engine.remote + "/dual_candidate.obj"
        engine.sftp.put(str(path), remote)
        if execute(engine.client, ["sha256sum", remote])["stdout"].split()[0] != sha256(path):
            raise ValueError("实际保存审计对象摘要不符")
        execution = execute(engine.client, [CHECKER, remote], timeout=120)
        certificate = {"saved_sha256": sha256(path), "execution": execution}
        if not execution["returncode"]:
            certificate.update(json.loads(execution["stdout"]))
        valid, metrics = mesh_valid_full_embedding(candidate, certificate)
        geometry = dual_reference_geometry(candidate, reference, maintenance)
        report.update(status="completed", finished_beijing=now(), result=details,
            saved_sha256=sha256(path), exact_embedding=certificate, output_metrics=metrics,
            geometry=geometry, accepted=bool(details["accepted"] and valid and geometry["worst_probe_max_mm"] <= .1))
        save(record, report)
        print("same_input_dual_reference_accepted", report["accepted"], geometry["worst_probe_max_mm"], flush=True)
    finally:
        engine.close()


if __name__ == "__main__":
    main()
