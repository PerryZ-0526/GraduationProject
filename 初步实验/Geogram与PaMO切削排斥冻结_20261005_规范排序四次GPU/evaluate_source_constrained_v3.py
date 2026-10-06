"""评估并冻结来源约束v3；正式挑战运行前必须核对冻结清单。"""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
from time import perf_counter
from zoneinfo import ZoneInfo

import numpy as np

from motion_record import load_document, replay_case
from surface_methods import (
    height_surface,
    mesh_quality,
    mesh_topology,
    sampled_surface_audit,
    source_constrained_height_surface,
    source_fitted_height_surface,
)


HERE = Path(__file__).resolve().parent
DEVELOPMENT_DOCUMENT = HERE / "quality_development_cases_v3.json"
EVALUATION_DOCUMENT = HERE / "quality_failure_cases_v2.json"
FREEZE_MANIFEST = HERE / "source_constrained_v3_freeze.json"
CORE_FILES = (
    HERE / "surface_methods.py",
    HERE / "test_motion_record.py",
    HERE / "screen_quality_development_cases.py",
    DEVELOPMENT_DOCUMENT,
    EVALUATION_DOCUMENT,
    Path(__file__).resolve(),
)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def core_hashes():
    return {path.name: sha256(path) for path in CORE_FILES}


def audit_case(case, policy, output):
    replay = replay_case(case, policy)
    target, target_diagnostics = height_surface(
        case,
        replay,
        (-2.0, 2.0, -2.0, 2.0),
        0.025,
    )
    raw, raw_diagnostics = height_surface(
        case,
        replay,
        (-2.0, 2.0, -2.0, 2.0),
        0.1,
    )
    legacy, legacy_diagnostics = source_fitted_height_surface(
        case,
        replay,
        (-2.0, 2.0, -2.0, 2.0),
        0.1,
    )
    started = perf_counter()
    constrained, constrained_diagnostics = (
        source_constrained_height_surface(
            case,
            replay,
            (-2.0, 2.0, -2.0, 2.0),
            0.1,
        )
    )
    elapsed_ms = (perf_counter() - started) * 1000.0

    prefix = case["id"]
    target_name = f"{prefix}_dense_target.vtp"
    constrained_name = f"{prefix}_source_constrained_v3.vtp"
    target.save(output / target_name)
    constrained.save(output / constrained_name)

    raw_quality = mesh_quality(raw)
    legacy_quality = mesh_quality(legacy)
    quality = mesh_quality(constrained)
    topology = mesh_topology(constrained)
    surface_audit = sampled_surface_audit(
        constrained,
        target,
        case,
        replay,
    )
    geometry_max = max(
        surface_audit[key]["max_mm"]
        for key in (
            "implicit_residual",
            "mesh_to_dense_target",
            "dense_target_to_mesh",
        )
    )
    failure_reasons = []
    if not constrained_diagnostics["height_graph_supported"]:
        failure_reasons.append("non_single_valued_vertical_wall")
    if quality["bad_faces"]:
        failure_reasons.append("shape_quality")
    if geometry_max > 0.1:
        failure_reasons.append("sampled_geometry")
    if (
        topology["connected_components"] != 1
        or topology["non_manifold_edges"]
        or topology["inconsistent_interior_edges"]
        or topology["self_intersection_faces"]
    ):
        failure_reasons.append("topology")

    expected = case["expected_raw_quality"]
    raw_checks = {
        "vertices": raw_quality["vertices"] == expected["vertices"],
        "faces": raw_quality["faces"] == expected["faces"],
        "bad_faces": raw_quality["bad_faces"] == expected["bad_faces"],
        "min_q": abs(raw_quality["min_q"] - expected["min_q"]) <= 1e-12,
        "min_angle_deg": (
            abs(raw_quality["min_angle_deg"] - expected["min_angle_deg"])
            <= 1e-12
        ),
        "all_removed_intervals_top_connected": (
            raw_diagnostics["all_removed_intervals_top_connected"]
            == expected["all_removed_intervals_top_connected"]
        ),
    }
    return {
        "case_id": case["id"],
        "screening_generation_index": case["screening_generation_index"],
        "raw_quality": raw_quality,
        "legacy_v2": {
            "quality": legacy_quality,
            "source_transition_continuous": legacy_diagnostics[
                "source_transition_continuous"
            ],
            "source_transition_max_one_sided_jump_mm": legacy_diagnostics[
                "source_transition_max_one_sided_jump_mm"
            ],
        },
        "source_constrained_v3": {
            "mesh": constrained_name,
            "elapsed_ms": elapsed_ms,
            "diagnostics": constrained_diagnostics,
            "quality": quality,
            "topology": topology,
            "sampled_surface_audit": surface_audit,
            "sampled_geometry_max_mm": geometry_max,
            "failure_reasons": failure_reasons,
            "accepted_for_this_case": not failure_reasons,
        },
        "dense_target": {
            "mesh": target_name,
            "diagnostics": target_diagnostics,
            "warning": "密集目标和近邻距离仍是抽样检查，不是连续误差证书",
        },
        "frozen_raw_checks": raw_checks,
        "completed": all(raw_checks.values()),
    }


def evaluate(dataset):
    document_path = (
        DEVELOPMENT_DOCUMENT
        if dataset == "development"
        else EVALUATION_DOCUMENT
    )
    if dataset == "evaluation":
        if not FREEZE_MANIFEST.exists():
            raise FileNotFoundError("正式挑战运行前缺少v3冻结清单")
        freeze = json.loads(FREEZE_MANIFEST.read_text(encoding="utf-8"))
        if core_hashes() != freeze["core_sha256"]:
            raise RuntimeError("核心文件已偏离v3冻结版本，拒绝运行挑战")

    document = load_document(document_path)
    timestamp = datetime.now(ZoneInfo("Asia/Shanghai")).strftime(
        "%Y%m%d_%H%M%S"
    )
    output = (
        HERE
        / "实验结果"
        / f"{timestamp}_source_constrained_v3_{dataset}"
    )
    output.mkdir(parents=True, exist_ok=False)
    rows = []
    for case in document["cases"]:
        row = audit_case(case, document["replay_policy"], output)
        rows.append(row)
        print(
            case["id"],
            row["source_constrained_v3"]["accepted_for_this_case"],
            flush=True,
        )
    result = {
        "schema_version": 1,
        "time_beijing": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
        "record_kind": "simulated",
        "dataset": dataset,
        "input_document": document_path.name,
        "input_document_sha256": sha256(document_path),
        "core_sha256": core_hashes(),
        "quality_gate": {
            "min_angle_deg": 25.0,
            "min_q": 0.4,
            "sampled_geometry_budget_mm": 0.1,
        },
        "cases": rows,
        "summary": {
            "cases_completed": sum(row["completed"] for row in rows),
            "case_count": len(rows),
            "height_graph_supported": sum(
                row["source_constrained_v3"]["diagnostics"][
                    "height_graph_supported"
                ]
                for row in rows
            ),
            "accepted": sum(
                row["source_constrained_v3"]["accepted_for_this_case"]
                for row in rows
            ),
            "legacy_v2_accepted_by_quality_and_continuity": sum(
                row["legacy_v2"]["quality"]["bad_faces"] == 0
                and row["legacy_v2"]["source_transition_continuous"]
                for row in rows
            ),
        },
        "interpretation": (
            "v3只接受连续高度交界；来源切换存在单侧高度差时，"
            "必须转入显式垂直壁三维重建，不能由高度图跨接"
        ),
    }
    result_path = output / "results.json"
    result_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(output)
    return result_path, result


def freeze(development_result_path):
    if FREEZE_MANIFEST.exists():
        raise FileExistsError(f"拒绝覆盖冻结清单: {FREEZE_MANIFEST}")
    path = Path(development_result_path).resolve()
    result = json.loads(path.read_text(encoding="utf-8"))
    if result["dataset"] != "development":
        raise ValueError("冻结依据必须是development结果")
    if result["core_sha256"] != core_hashes():
        raise RuntimeError("开发结果与当前核心文件哈希不一致")
    if result["summary"] != {
        "cases_completed": 8,
        "case_count": 8,
        "height_graph_supported": 7,
        "accepted": 7,
        "legacy_v2_accepted_by_quality_and_continuity": 5,
    }:
        raise RuntimeError("开发结果未达到预注册的连续域7/7验收边界")
    manifest = {
        "schema_version": 1,
        "algorithm_version": "source_constrained_v3",
        "frozen_at_beijing": datetime.now(
            ZoneInfo("Asia/Shanghai")
        ).isoformat(),
        "core_sha256": core_hashes(),
        "development_results": str(path.relative_to(HERE)),
        "development_results_sha256": sha256(path),
        "development_summary": result["summary"],
        "challenge_not_run_by_this_evaluator_before_freeze": True,
        "fixed_policy": {
            "source_snap_fraction": 0.35,
            "transition_continuity_tolerance_mm": 1e-8,
            "constraint_search_samples": 33,
            "constraint_search_levels": 3,
            "constraint_optimization_sweeps": 3,
            "quality_min_angle_deg": 25.0,
            "quality_min_q": 0.4,
            "sampled_geometry_budget_mm": 0.1,
        },
    }
    FREEZE_MANIFEST.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(FREEZE_MANIFEST)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset",
        choices=("development", "evaluation"),
    )
    parser.add_argument("--freeze-development-results", type=Path)
    args = parser.parse_args()
    if bool(args.dataset) == bool(args.freeze_development_results):
        parser.error("必须且只能指定--dataset或--freeze-development-results")
    if args.dataset:
        evaluate(args.dataset)
    else:
        freeze(args.freeze_development_results)


if __name__ == "__main__":
    main()
