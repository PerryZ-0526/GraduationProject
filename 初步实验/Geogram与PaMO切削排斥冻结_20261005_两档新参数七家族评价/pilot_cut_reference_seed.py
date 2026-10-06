"""复用公开骨面GPU原始输出，对照参照恢复与恢复后的整面排斥。"""

import argparse
import json
from pathlib import Path
import sys
from time import perf_counter

import numpy as np
import trimesh

# 只读取已结束批次的冻结依赖，避免另一聊天修改共享模块改变本次开发消融。
SNAPSHOT = Path(__file__).parents[1] / "Geogram与PaMO切削排斥冻结_20261004_保留配对"
sys.path.insert(0, str(SNAPSHOT))
from pilot_cut_exclusion import nearest_projection
from adaptive_cut_exclusion import adaptive_exclusion
from audit_followup_candidate import sha256, quality_distribution
from audit_cut_delivery import probes
from exact_alarm_contact import mesh_valid_exact_contacts
from run_constrained_feedback import global_geometry
from locality_masks import save_obj_fp64
from run_geometry_study import save, now


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    batch_path = args.batch / "01-反馈执行与独立审计.json"
    batch = json.loads(batch_path.read_text("utf8"))
    if batch["status"] == "running":
        raise ValueError("公开批次仍运行，不能开启已见开发消融")
    manifest = json.loads((args.prepared / "01-完整范围冻结清单.json").read_text("utf8"))
    args.output.mkdir(exist_ok=False)
    (args.output / Path(__file__).name).write_bytes(Path(__file__).read_bytes())
    report = {"生成时间": now(), "修改时间及修改内容": "首次生成，开发消融不改写原协议",
              "文档概述": "先参照恢复，再整面排斥；修正预算相对恢复种子，原始GPU位移另报",
              "索引目录": ["protocol", "rows"], "status": "running", "rows": [],
              "batch_sha256": sha256(batch_path), "snapshot_sha256": sha256(SNAPSHOT / "01-执行源码冻结清单.json"),
              "protocol": {"development_seen_inputs": True, "new_gpu_calls": 0,
                  "restoration": "nearest_points_on_independent_first_cut_reference_same_faces",
                  "exclusion_correction_budget_mm_from_restored_seed": .1,
                  "original_raw_displacement_budget_enforced": False,
                  "target_geometry_probe_budget_mm": .1, "max_refinement_levels": 2,
                  "full_exact_embedding_certificate": "separate_remote_audit_required",
                  "continuous_target_geometry_certificate": False}}
    record = args.output / "01-参照恢复与整面排斥开发消融.json"
    save(record, report)
    for route in manifest["routes"]:
        rid, eid = route["id"], route["cutting_prefix_ids"][0]
        folder = args.batch / f"{rid}_{eid}_full_full"
        raw_path = folder / "raw_for_equal_input_reuse.obj"
        if not raw_path.exists():
            report["rows"].append({"route": rid, "status": "raw_GPU_output_unavailable"})
            save(record, report)
            continue
        reference_folder = args.batch / f"{rid}_{eid}_reference"
        reference_path = reference_folder / "validated_reference.obj"
        if not reference_path.exists():
            reference_path = reference_folder / "reference.obj"
        reference = trimesh.load(reference_path, force="mesh", process=True, validate=True)
        raw = trimesh.load(raw_path, force="mesh", process=False)
        tool_path = args.prepared / "inputs" / route["prefix_tools"][0]["mesh"]
        tool = trimesh.load(tool_path, force="mesh", process=False)
        start = perf_counter()
        restored = nearest_projection(raw, reference)
        displacement = float(np.linalg.norm(restored.vertices - raw.vertices, axis=1).max(initial=0))
        exclusion, details = adaptive_exclusion(restored, [tool], reference)
        row = {"route": rid, "raw_sha256": sha256(raw_path), "reference_sha256": sha256(reference_path),
               "tool_sha256": sha256(tool_path), "restoration_max_raw_displacement_mm": displacement,
               "CPU_total_ms": (perf_counter() - start) * 1000, "exclusion": details, "methods": {}}
        for name, mesh in (("restore_only", restored), ("restore_then_exclude", exclusion)):
            path = args.output / f"{rid}_{name}.obj"
            save_obj_fp64(mesh, path)
            # 重新加载实际保存对象后审查，预检查不能代替独立全网格精确嵌入证书。
            saved = trimesh.load(path, force="mesh", process=False)
            valid, checks = mesh_valid_exact_contacts(saved)
            geometry = global_geometry(saved, reference)
            row["methods"][name] = {"saved_sha256": sha256(path), "mesh_valid_precheck": valid,
                "checks": checks, "geometry": geometry, "quality": quality_distribution(saved),
                "probes": probes(saved, [tool]), "preliminary_pass": bool(valid and geometry["probe_max_mm"] <= .1
                    and (name == "restore_only" or details["accepted"]))}
        report["rows"].append(row)
        save(record, report)
        print(rid, "raw_move", displacement, {k: v["preliminary_pass"] for k, v in row["methods"].items()}, flush=True)
    report.update(status="completed_development_pending_full_embedding_audit", finished_beijing=now())
    save(record, report)


if __name__ == "__main__":
    main()
