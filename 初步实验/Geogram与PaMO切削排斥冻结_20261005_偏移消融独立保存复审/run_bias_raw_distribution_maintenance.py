"""对三档偏移的六张同源原GPU输出应用同一分布排斥维护与保存嵌入审计。"""

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
from distribution_ranked_exclusion import distribution_ranked_exclusion
from geometry_error_distribution import geometry_error_distribution, cutting_surface_distribution


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("prepared", "previous", "side-validation", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--probes", type=Path, nargs=3, required=True)
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    old_path = args.previous / "01-统一配置完整父反馈记录.json"
    old = json.loads(old_path.read_text("utf8"))
    rid = old["selected_route"]
    event = next(row for row in old["rows"] if row["event"] == "e1")
    stem = rid + "_e1"
    source = args.previous / (stem + "_candidate_input") / "clean_source.obj"
    labels = source.with_name("clean_labels.json")
    reference_path = args.previous / (stem + "_reference") / "validated_reference.obj"
    if not reference_path.exists():
        reference_path = reference_path.with_name("reference.obj")
    for path, expected in ((source, event["attempt"]["inputs_sha256"]["source.obj"]),
                           (labels, event["attempt"]["inputs_sha256"]["labels.json"]),
                           (reference_path, event["reference_sha256"])):
        if sha256(path) != expected:
            raise ValueError("实际源、标签或独立参照摘要改变")
    probes = []
    for root in args.probes:
        path = root / "01-简化邻接顺序同输入完整对照.json"
        probe = json.loads(path.read_text("utf8"))
        if probe["status"] != "completed" or probe["previous_record_sha256"] != sha256(old_path) or probe["selected_event"] != "e1" or len(probe["rows"]) != 2:
            raise ValueError("要求三档同一真实事件的完整两次GPU记录")
        for row in probe["rows"]:
            if row["execution"]["returncode"] or row["capacity_overflow"] or not row["capacity_declared_67108864"]:
                raise ValueError("GPU执行或容量记录无效")
        probes.append((root, probe, sha256(path)))
    if sorted(probe["offset_factor"] for _, probe, _ in probes) != [0.0, 0.45, 0.9]:
        raise ValueError("必须保留原偏移、半偏移、零偏移三档完整分母")
    args.output.mkdir(exist_ok=False)
    ReferenceCutEngine.prepared, ReferenceCutEngine.side_validation = args.prepared, args.side_validation
    engine = ReferenceCutEngine(args.output, args.port)
    report = {"生成时间": now(), "修改时间及修改内容": "首次生成，六张真实GPU输出同版静态维护",
              "文档概述": "同一第二刀源和累计工具，不是连续反馈或未见评价；无固定几何合格率",
              "索引目录": ["bindings", "rows"], "status": "running", "new_GPU_calls": 0,
              "planned_maintenance_calls": 6, "geometry_quality_decision": "statistics_only_pending_evaluation",
              "bindings": {"previous_sha256": sha256(old_path), "source_sha256": sha256(source),
                           "labels_sha256": sha256(labels), "reference_sha256": sha256(reference_path)}, "rows": []}
    record = args.output / "01-三档偏移六输出同版维护与保存复审.json"
    save(record, report)
    try:
        report["environment"] = engine.setup()
        maintenance = trimesh.load(source, force="mesh", process=False)
        reference = trimesh.load(reference_path, force="mesh", process=True)
        bits = json.loads(labels.read_text("utf8"))["operand_bits"]
        tools = []
        for entry in engine.routes[rid]["prefix_tools"]:
            if entry["event_id"] not in ("e0", "e1"):
                continue
            path = args.prepared / "inputs" / entry["mesh"]
            if sha256(path) != entry["sha256"]:
                raise ValueError("累计工具摘要改变")
            tools.append(trimesh.load(path, force="mesh", process=False))
        if len(tools) != 2:
            raise ValueError("第二刀必须绑定两个累计工具")
        for root, probe, digest in probes:
            for index, gpu in enumerate(probe["rows"], 1):
                raw_path = root / f"同输入GPU第{index}次" / "candidate.obj"
                if sha256(raw_path) != gpu["output_sha256"]:
                    raise ValueError("原GPU保存对象摘要改变")
                name = f"偏移{probe['offset_factor']}_重复{index}"
                folder = args.output / name
                folder.mkdir()
                row = {"offset_factor": probe["offset_factor"], "repeat": index, "raw_sha256": sha256(raw_path),
                       "probe_record_sha256": digest, "status": "running"}
                report["rows"].append(row)
                save(record, report)
                started = perf_counter()
                raw = trimesh.load(raw_path, force="mesh", process=False)
                candidate, details = distribution_ranked_exclusion(raw, tools, reference, maintenance, bits, engine.side.anchor)
                path = folder / "candidate.obj"
                save_obj_fp64(candidate, path)
                remote = engine.remote + "/" + name + ".obj"
                engine.sftp.put(str(path), remote)
                if execute(engine.client, ["sha256sum", remote])["stdout"].split()[0] != sha256(path):
                    raise ValueError("完整嵌入实际对象摘要不符")
                execution = execute(engine.client, [CHECKER, remote], timeout=120)
                certificate = {"saved_sha256": sha256(path), "execution": execution}
                if not execution["returncode"]:
                    certificate.update(json.loads(execution["stdout"]))
                valid, metrics = mesh_valid_full_embedding(candidate, certificate)
                same_topology = candidate.euler_number == maintenance.euler_number and len(candidate.split(only_watertight=False)) == len(maintenance.split(only_watertight=False))
                # 合法性单独审查，误差分布和最大值均不替代材料排斥与保存嵌入证书。
                row.update(status="completed", result=details, saved_sha256=sha256(path), exact_embedding=certificate,
                    output_metrics=metrics, same_topology_as_source=same_topology,
                    accepted_geometry_observation=bool(details["accepted"] and valid and same_topology),
                    cumulative_distribution=geometry_error_distribution(candidate, reference),
                    source_distribution=geometry_error_distribution(candidate, maintenance),
                    cutting_surface_distribution=cutting_surface_distribution(candidate, maintenance, bits),
                    quality=quality_distribution(candidate), maintenance_ms=(perf_counter() - started) * 1000)
                save(record, report)
                print(name, row["accepted_geometry_observation"], flush=True)
        report.update(status="completed", finished_beijing=now())
        save(record, report)
    finally:
        engine.close()


if __name__ == "__main__":
    main()
