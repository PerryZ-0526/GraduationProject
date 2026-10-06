"""冻结显式垂直壁方法的开发案例，不运行壁面生成器。"""
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
from surface_methods import (
    _axis,
    _scan_grid_source_transitions,
    height_surface,
    mesh_quality,
    top_connected_height,
)


HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "vertical_wall_development_cases_v1.json"
EXCLUDED_INDICES = {
    0,
    15,
    24,
    30,
    123,
    124,
    132,
    138,
    240,
    247,
    267,
    282,
    348,
    356,
    391,
    392,
}
FROZEN_AT = "2026-09-18 01:24:00"


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
    regular_axis = _axis((-2.0, 2.0), 0.1)
    regular_xy = np.stack(
        np.meshgrid(regular_axis, regular_axis, indexing="ij"),
        axis=-1,
    )
    selected = {slope: [] for slope in PLANE_A}
    discontinuous_count = 0
    parameters = itertools.product(
        PLANE_A,
        PLANE_B,
        RADII,
        SHIFTS,
        Z_DELTAS,
    )
    for index, values in enumerate(parameters):
        if index in EXCLUDED_INDICES:
            continue
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
        _, _, dense_diagnostics = top_connected_height(
            dense_xy,
            case,
            replay,
        )
        if not dense_diagnostics["all_removed_intervals_top_connected"]:
            continue
        transitions = _scan_grid_source_transitions(
            regular_xy,
            case,
            replay,
        )
        if transitions["global_discontinuous_source_transition_count"] == 0:
            continue
        discontinuous_count += 1
        selected[values[0]].append(
            {
                "generation_index": index,
                "parameters": values,
                "quality": quality,
                "transitions": transitions,
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
                -row["transitions"][
                    "global_discontinuous_source_transition_count"
                ],
                -row["transitions"][
                    "global_source_transition_max_one_sided_jump_mm"
                ],
                row["generation_index"],
            ),
        )
        if ranked:
            rows.append(ranked[0])
    return {
        "discontinuous_candidate_count": discontinuous_count,
        "selected": rows,
    }


def make_document(result):
    cases = []
    for row in result["selected"]:
        case = row["case"]
        case["id"] = (
            f"vertical_wall_development_{row['generation_index']:03d}"
        )
        case["split"] = "development"
        case["purpose"] = (
            "与既有开发及评测隔离的非连续高度边界显式壁面开发案例"
        )
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
            key: row["quality"][key]
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
        case["expected_source_transitions"] = row["transitions"]
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
        "frozen_before_explicit_wall_run": FROZEN_AT,
        "screening": {
            "purpose": (
                "只按原始坏面、密集适用域和v3冻结的来源跳变扫描"
                "选择显式壁面开发案例"
            ),
            "explicit_wall_not_run_before_freeze": True,
            "excluded_previously_used_generation_indices": sorted(
                EXCLUDED_INDICES
            ),
            "candidate_spacing_mm": 0.1,
            "dense_scope_spacing_mm": 0.025,
            "transition_scan_spacing_mm": 0.025,
            "selection_rule": (
                "每个plane_a层按非连续切换数降序、最大单侧高度差"
                "降序、生成编号升序取一条"
            ),
            "discontinuous_candidate_count": result[
                "discontinuous_candidate_count"
            ],
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
            "transition_continuity_tolerance_mm": 1e-8,
        },
        "cases": cases,
    }


def verify(result, document):
    screening = document["screening"]
    assert (
        result["discontinuous_candidate_count"]
        == screening["discontinuous_candidate_count"]
    )
    assert [
        row["generation_index"] for row in result["selected"]
    ] == screening["selected_generation_indices"]
    for generated, frozen in zip(result["selected"], document["cases"]):
        expected = frozen["expected_raw_quality"]
        for key in ("vertices", "faces", "bad_faces"):
            assert generated["quality"][key] == expected[key]
        for key in ("min_q", "min_angle_deg"):
            assert abs(generated["quality"][key] - expected[key]) <= 1e-12
        assert generated["transitions"] == frozen[
            "expected_source_transitions"
        ]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
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
                "discontinuous_candidate_count": result[
                    "discontinuous_candidate_count"
                ],
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
