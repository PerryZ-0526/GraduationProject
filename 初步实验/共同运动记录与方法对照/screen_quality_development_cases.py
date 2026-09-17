"""冻结并复核与正式挑战隔离的质量失败开发集。"""
import argparse
import hashlib
import itertools
import json
from pathlib import Path

import numpy as np

from motion_record import load_document, replay_case
from screen_quality_failure_cases import (
    PLANE_A,
    PLANE_B,
    RADII,
    SHIFTS,
    Z_DELTAS,
    make_case,
)
from surface_methods import height_surface, mesh_quality, top_connected_height


HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "quality_development_cases_v3.json"
FROZEN_EVALUATION_INDICES = {15, 30, 132, 138, 240, 247, 348, 356}
FROZEN_AT = "2026-09-18 01:06:23"


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def screen():
    policy = {
        "late_event": "reject",
        "max_link_gap_ms": 200,
        "interpolate_missing_motion": False,
    }
    dense_axis = np.linspace(-2.0, 2.0, 161)
    dense_xy = np.stack(
        np.meshgrid(dense_axis, dense_axis, indexing="ij"),
        axis=-1,
    )
    selected = {slope: [] for slope in PLANE_A}
    raw_failure_count = 0
    dense_scope_raw_failure_count = 0
    parameters = itertools.product(
        PLANE_A,
        PLANE_B,
        RADII,
        SHIFTS,
        Z_DELTAS,
    )
    for index, values in enumerate(parameters):
        case = make_case(index, values)
        replay = replay_case(case, policy)
        mesh, _ = height_surface(
            case,
            replay,
            (-2.0, 2.0, -2.0, 2.0),
            0.1,
        )
        quality = mesh_quality(mesh)
        if quality["bad_faces"] == 0:
            continue
        raw_failure_count += 1
        _, _, dense_diagnostics = top_connected_height(
            dense_xy,
            case,
            replay,
        )
        if not dense_diagnostics["all_removed_intervals_top_connected"]:
            continue
        dense_scope_raw_failure_count += 1
        if index in FROZEN_EVALUATION_INDICES:
            continue
        selected[values[0]].append(
            {
                "generation_index": index,
                "parameters": values,
                "quality": quality,
                "dense_scope_internal_cavity_samples": dense_diagnostics[
                    "internal_cavity_sample_count"
                ],
                "case": case,
            }
        )

    rows = []
    for slope in PLANE_A:
        ranked = sorted(
            selected[slope],
            key=lambda row: (
                -row["quality"]["bad_faces"],
                row["generation_index"],
            ),
        )
        rows.extend(ranked[:2])
    return {
        "screened_case_count": (
            len(PLANE_A)
            * len(PLANE_B)
            * len(RADII)
            * len(SHIFTS)
            * len(Z_DELTAS)
        ),
        "raw_failure_count": raw_failure_count,
        "dense_scope_raw_failure_count": dense_scope_raw_failure_count,
        "selected": rows,
    }


def make_document(result):
    cases = []
    for row in result["selected"]:
        case = row["case"]
        case["id"] = (
            f"development_v3_raw_failure_{row['generation_index']:03d}"
        )
        case["split"] = "development"
        case["purpose"] = (
            "与冻结挑战隔离的多来源交线和约束三角化开发案例"
        )
        quality = row["quality"]
        case["screening_generation_index"] = row["generation_index"]
        case["screening_parameters"] = dict(
            zip(
                (
                    "plane_a",
                    "plane_b",
                    "tool_radius_mm",
                    "path_shift_mm",
                    "endpoint_z_delta_mm",
                ),
                row["parameters"],
            )
        )
        case["expected_raw_quality"] = {
            key: quality[key]
            for key in (
                "vertices",
                "faces",
                "bad_faces",
                "min_q",
                "min_angle_deg",
            )
        }
        case["expected_raw_quality"].update(
            {
                "all_removed_intervals_top_connected": True,
                "dense_scope_internal_cavity_samples": row[
                    "dense_scope_internal_cavity_samples"
                ],
            }
        )
        cases.append(case)

    return {
        "schema_version": 1,
        "record_kind": "simulated",
        "coordinate_frame": {
            "name": "bone",
            "length_unit": "mm",
            "time_unit": "ms",
            "handedness": "right",
        },
        "replay_policy": {
            "late_event": "reject",
            "max_link_gap_ms": 200,
            "interpolate_missing_motion": False,
        },
        "baselines": [],
        "frozen_before_constrained_source_run": FROZEN_AT,
        "screening": {
            "purpose": (
                "仅用原始候选和密集适用域检查建立算法开发集；"
                "不以任何来源修复结果选择案例"
            ),
            "raw_only_screening": True,
            "constrained_source_not_run_before_freeze": True,
            "surface_methods_sha256_before_development": sha256(
                HERE / "surface_methods.py"
            ),
            "frozen_evaluation_generation_indices_excluded": sorted(
                FROZEN_EVALUATION_INDICES
            ),
            "xy_bounds_mm": [-2.0, 2.0, -2.0, 2.0],
            "candidate_spacing_mm": 0.1,
            "dense_scope_spacing_mm": 0.025,
            "screened_case_count": result["screened_case_count"],
            "raw_failure_count": result["raw_failure_count"],
            "dense_scope_raw_failure_count": result[
                "dense_scope_raw_failure_count"
            ],
            "selection_rule": (
                "排除两版冻结评测已执行编号后，每个plane_a层按raw "
                "bad_faces降序、生成编号升序取前两条"
            ),
            "selected_generation_indices": [
                row["generation_index"] for row in result["selected"]
            ],
        },
        "parameter_policy": {
            "candidate_xy_spacing_mm": 0.1,
            "dense_target_spacing_mm": 0.025,
            "quality_min_angle_deg": 25.0,
            "quality_min_q": 0.4,
            "sampled_geometry_budget_mm": 0.1,
        },
        "cases": cases,
    }


def verify(result, document):
    screening = document["screening"]
    assert result["screened_case_count"] == screening["screened_case_count"]
    assert result["raw_failure_count"] == screening["raw_failure_count"]
    assert (
        result["dense_scope_raw_failure_count"]
        == screening["dense_scope_raw_failure_count"]
    )
    assert [
        row["generation_index"] for row in result["selected"]
    ] == screening["selected_generation_indices"]
    for generated, frozen in zip(result["selected"], document["cases"]):
        expected = frozen["expected_raw_quality"]
        actual = generated["quality"]
        for key in ("vertices", "faces", "bad_faces"):
            assert actual[key] == expected[key]
        for key in ("min_q", "min_angle_deg"):
            assert abs(actual[key] - expected[key]) <= 1e-12
        assert (
            generated["dense_scope_internal_cavity_samples"]
            == expected["dense_scope_internal_cavity_samples"]
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--write",
        action="store_true",
        help="首次冻结开发集；目标已存在时拒绝覆盖",
    )
    args = parser.parse_args()
    result = screen()
    if args.write:
        if OUTPUT.exists():
            raise FileExistsError(f"拒绝覆盖已冻结开发集: {OUTPUT}")
        OUTPUT.write_text(
            json.dumps(make_document(result), ensure_ascii=False, indent=2)
            + "\n",
            encoding="utf-8",
        )
    document = load_document(OUTPUT)
    verify(result, document)
    print(
        json.dumps(
            {
                "status": "passed",
                "selected_generation_indices": document["screening"][
                    "selected_generation_indices"
                ],
                "sha256": sha256(OUTPUT),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
