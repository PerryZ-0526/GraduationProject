"""同一实际GPU对象比较原版、仅参照恢复与完整候选，不冒称独立父反馈路线。"""

import argparse
import json
from pathlib import Path

import trimesh

from run_reference_cut_feedback import ReferenceCutEngine
from run_geometry_study import execute, save, now
from audit_followup_candidate import sha256, quality_distribution
from audit_cut_embedding import CHECKER
from audit_cut_delivery import probes
from exact_embedding_gate import mesh_valid_full_embedding
from run_constrained_feedback import global_geometry
from pilot_cut_exclusion import nearest_projection
from locality_masks import save_obj_fp64


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    batch_path = args.batch / "01-统一配置完整父反馈记录.json"
    batch = json.loads(batch_path.read_text("utf8"))
    manifest_path = args.prepared / "01-完整范围冻结清单.json"
    if batch["status"] == "running" or sha256(manifest_path) != batch["manifest_sha256"]:
        raise ValueError("批次未终止或输入清单不符")
    args.output.mkdir(exist_ok=False)
    ReferenceCutEngine.prepared = args.prepared
    engine = ReferenceCutEngine(args.output, args.port)
    route = engine.routes[batch.get("selected_route", next(iter(engine.routes)))]
    rid = route["id"]
    report = {"生成时间": now(), "修改时间及修改内容": "首次生成，固定实际输入的恢复消融",
              "文档概述": "第二刀起原版对象也来自候选父链，不能称原版完整连续路线",
              "索引目录": ["rows", "summary"], "status": "running", "rows": [],
              "source_batch_sha256": sha256(batch_path), "new_GPU_calls": 0}
    record = args.output / "01-原版恢复与完整候选同输入消融.json"
    try:
        if execute(engine.client, ["mkdir", engine.remote])["returncode"]:
            raise ValueError("消融远端目录已存在")
        actual = execute(engine.client, ["sha256sum", CHECKER])["stdout"].split()[0]
        if actual != batch["environment"]["exact_embedding_checker_sha256"]:
            raise ValueError("完整检查器摘要改变")
        report["exact_checker_sha256"] = actual
        save(record, report)
        for row in batch["rows"]:
            if "attempt" not in row or row["attempt"]["execution"]["returncode"]:
                continue
            event = row["event"]
            folder = args.batch / f"{rid}_{event}_candidate_boolean"
            raw_path = folder / "raw_full_candidate.obj"
            if sha256(raw_path) != row["attempt"]["raw_full_output_sha256"]:
                raise ValueError("实际GPU原对象已改变")
            source_path = args.batch / f"{rid}_{event}_candidate_input/clean_source.obj"
            if sha256(source_path) != row["attempt"]["inputs_sha256"]["source.obj"]:
                raise ValueError("GPU输入源摘要已改变")
            source = trimesh.load(source_path, force="mesh", process=False)
            reference_folder = args.batch / f"{rid}_{event}_reference"
            reference_path = reference_folder / "validated_reference.obj"
            if not reference_path.exists():
                reference_path = reference_folder / "reference.obj"
            reference = trimesh.load(reference_path, force="mesh", process=True, validate=True)
            prefix = set(route["cutting_prefix_ids"][:route["cutting_prefix_ids"].index(event) + 1])
            tool_paths = [args.prepared / "inputs" / t["mesh"] for t in route["prefix_tools"] if t["event_id"] in prefix]
            if [sha256(p) for p in tool_paths] != row["attempt"]["cut_exclusion"]["cumulative_tool_sha256"]:
                raise ValueError("累计工具摘要改变")
            tools = [trimesh.load(p, force="mesh", process=False) for p in tool_paths]
            raw = trimesh.load(raw_path, force="mesh", process=False)
            restored = nearest_projection(raw, reference)
            for method, mesh in (("原版GPU", raw), ("仅参照恢复", restored),
                                 ("完整候选", trimesh.load(folder / "candidate.obj", force="mesh", process=False))):
                path = args.output / f"{event}_{method}.obj"
                # 三个控制均按同一17位FP64格式保存，原GPU文件摘要另由上游记录绑定。
                save_obj_fp64(mesh, path)
                remote = engine.remote + "/" + path.name
                engine.sftp.put(str(path), remote)
                if execute(engine.client, ["sha256sum", remote])["stdout"].split()[0] != sha256(path):
                    raise ValueError("实际消融审计对象摘要不符")
                run = execute(engine.client, [CHECKER, remote], timeout=120)
                certificate = {"saved_sha256": sha256(path), "execution": run}
                if not run["returncode"]:
                    certificate.update(json.loads(run["stdout"]))
                # 重新加载实际保存对象，只使用检查器实际读取的文件摘要。
                checked = trimesh.load(path, force="mesh", process=False)
                valid, metrics = mesh_valid_full_embedding(checked, certificate)
                geometry = global_geometry(checked, reference)
                entry = {"event": event, "method": method, "saved_sha256": sha256(path),
                         "exact_embedding": certificate, "mesh_valid": valid, "metrics": metrics,
                         "source_geometry": global_geometry(checked, source), "cumulative_geometry": geometry,
                         "quality": quality_distribution(checked), "cut_probes": probes(checked, tools)}
                entry["passes_geometry_and_embedding_only"] = bool(valid and geometry["probe_max_mm"] <= .1
                    and entry["source_geometry"]["probe_max_mm"] <= .1)
                report["rows"].append(entry)
                save(record, report)
                print(event, method, "geometry_embedding", entry["passes_geometry_and_embedding_only"], flush=True)
        report.update(status="completed", finished_beijing=now(), summary={"controls": len(report["rows"]),
            "complete_original_feedback_certified": False, "continuous_target_distance_certified": False})
        save(record, report)
    finally:
        engine.close()


if __name__ == "__main__":
    main()
