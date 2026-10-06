"""四张实际GPU输出分别配对旧维护与双参照维护，不新增GPU或择优输入。"""

import argparse
import json
from pathlib import Path
from time import perf_counter

import trimesh
from run_reference_cut_feedback import ReferenceCutEngine
from run_geometry_study import execute, save, now
from audit_followup_candidate import sha256, quality_distribution
from audit_cut_embedding import CHECKER
from locality_masks import save_obj_fp64
from exact_embedding_gate import mesh_valid_full_embedding
from stepwise_coverage_exclusion import stepwise_coverage_exclusion
from dual_reference_coverage_exclusion import dual_reference_coverage_exclusion, dual_reference_geometry


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("prepared", "previous", "side-validation", "gpu-probe", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    args.output.mkdir(exist_ok=False)
    rid = "BP3D_FJ3384_交叉浅磨"
    old_path = args.previous / "01-统一配置完整父反馈记录.json"
    old = json.loads(old_path.read_text("utf8"))
    previous = old["rows"][0]["attempt"]
    source = args.previous / f"{rid}_e0_candidate_input/clean_source.obj"
    reference_path = args.previous / f"{rid}_e0_reference/validated_reference.obj"
    if not reference_path.exists():
        reference_path = reference_path.with_name("reference.obj")
    if sha256(source) != previous["inputs_sha256"]["source.obj"] or sha256(reference_path) != previous["cut_exclusion"]["cumulative_reference_sha256"]:
        raise ValueError("固定维护源或累计参照已改变")
    probe_path = args.gpu_probe / "01-同几何排列完整GPU冻结对照.json"
    probe = json.loads(probe_path.read_text("utf8"))
    if probe["status"] != "completed" or len(probe["rows"]) != 4 or any(row["execution"]["returncode"] for row in probe["rows"]):
        raise ValueError("四次实际GPU终态不完整")
    report = {"生成时间": now(), "修改时间及修改内容": "首次生成，四张GPU输出各两种维护固定配对",
              "文档概述": "同原始GPU对象、同维护源、同累计参照和同工具；不算连续路线或新增GPU",
              "索引目录": ["bindings", "protocol", "rows"], "status": "running", "new_GPU_calls": 0,
              "bindings": {"source_sha256": sha256(source), "reference_sha256": sha256(reference_path),
                           "gpu_record_sha256": sha256(probe_path), "previous_record_sha256": sha256(old_path)},
              "protocol": {"raw_inputs": [row["name"] for row in probe["rows"]], "methods": ["stepwise", "dual_reference"],
                           "distance_budget_mm": .1, "planned_maintenance_calls": 8}, "rows": []}
    record = args.output / "01-四张同原始GPU输出维护配对.json"
    ReferenceCutEngine.prepared, ReferenceCutEngine.side_validation = args.prepared, args.side_validation
    engine = ReferenceCutEngine(args.output, args.port)
    save(record, report)
    try:
        report["environment"] = engine.setup()
        reference = trimesh.load(reference_path, force="mesh", process=True, validate=True)
        maintenance = trimesh.load(source, force="mesh", process=False)
        entry = next(tool for tool in engine.routes[rid]["prefix_tools"] if tool["event_id"] == "e0")
        tool_path = args.prepared / "inputs" / entry["mesh"]
        if sha256(tool_path) != entry["sha256"] or sha256(tool_path) != probe["tool_sha256"]:
            raise ValueError("实际首刀累计工具不一致")
        tools = [trimesh.load(tool_path, force="mesh", process=False)]
        report["bindings"]["tool_sha256"] = sha256(tool_path)
        report["mechanism_sha256"] = {name: sha256(Path(__file__).with_name(name + ".py")) for name in ("stepwise_coverage_exclusion", "dual_reference_coverage_exclusion")}
        save(record, report)
        for raw_row in probe["rows"]:
            raw_path = args.gpu_probe / raw_row["name"] / "candidate.obj"
            if sha256(raw_path) != raw_row["output_sha256"]:
                raise ValueError("实际原GPU输出摘要不同")
            for method in report["protocol"]["methods"]:
                name = raw_row["name"] + "_" + method
                folder = args.output / name
                folder.mkdir()
                row = {"raw_name": raw_row["name"], "raw_sha256": sha256(raw_path), "method": method, "status": "running"}
                report["rows"].append(row)
                save(record, report)
                raw = trimesh.load(raw_path, force="mesh", process=False)
                started = perf_counter()
                if method == "stepwise":
                    candidate, details = stepwise_coverage_exclusion(raw, tools, reference, engine.side.anchor)
                else:
                    candidate, details = dual_reference_coverage_exclusion(raw, tools, reference, maintenance, engine.side.anchor)
                row["maintenance_ms"] = (perf_counter() - started) * 1000
                path = folder / "candidate.obj"
                save_obj_fp64(candidate, path)
                remote = engine.remote + "/" + name + ".obj"
                engine.sftp.put(str(path), remote)
                if execute(engine.client, ["sha256sum", remote])["stdout"].split()[0] != sha256(path):
                    raise ValueError("完整嵌入审计对象摘要不符")
                execution = execute(engine.client, [CHECKER, remote], timeout=120)
                certificate = {"saved_sha256": sha256(path), "execution": execution}
                if not execution["returncode"]:
                    certificate.update(json.loads(execution["stdout"]))
                valid, metrics = mesh_valid_full_embedding(candidate, certificate)
                geometry = dual_reference_geometry(candidate, reference, maintenance)
                # 两种方法均按最终双参照门槛评价，内部旧停止条件不能冒充通过。
                row.update(status="completed", result=details, saved_sha256=sha256(path), exact_embedding=certificate,
                           output_metrics=metrics, geometry=geometry, quality=quality_distribution(candidate),
                           accepted=bool(details["accepted"] and valid and geometry["worst_probe_max_mm"] <= .1))
                save(record, report)
                print(name, row["accepted"], geometry["worst_probe_max_mm"], flush=True)
        report.update(status="completed", finished_beijing=now())
        save(record, report)
    finally:
        engine.close()


if __name__ == "__main__":
    main()
