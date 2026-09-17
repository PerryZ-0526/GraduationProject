"""复现质量失败挑战集筛选；本模块不导入或运行来源修复。"""
import argparse
import itertools
import json
from pathlib import Path

import numpy as np

from motion_record import load_document, replay_case
from surface_methods import height_surface, mesh_quality, top_connected_height


HERE = Path(__file__).resolve().parent
PLANE_A = (0.11, 0.15, 0.19, 0.23)
PLANE_B = (-0.14, -0.10, -0.06)
RADII = (0.66, 0.70, 0.74)
SHIFTS = (-0.06, -0.02, 0.02, 0.06)
Z_DELTAS = (-0.04, 0.0, 0.04)
EXCLUDED_INDICES = {30, 138, 240, 348}


def make_case(index, parameters):
    a, b, radius, shift, z_delta = parameters
    positions = [
        [-1.0 + shift, -1.0 - shift, 0.45 + z_delta],
        [1.0 + shift, 1.0 - shift, 0.55 - z_delta],
        [-1.0 - shift, 1.0 + shift, 0.50 - z_delta],
        [1.0 - shift, -1.0 + shift, 0.50 + z_delta],
    ]
    events = []
    for event_id, timestamp, position, cutting, connected in [
        ("a0", 0, positions[0], True, False),
        ("a1", 100, positions[1], True, True),
        ("pause", 150, positions[1], False, False),
        ("b0", 200, positions[2], True, False),
        ("b1", 300, positions[3], True, True),
    ]:
        events.append(
            {
                "id": event_id,
                "arrival_index": len(events),
                "timestamp_ms": timestamp,
                "position_mm": position,
                "orientation_xyzw": [0.0, 0.0, 0.0, 1.0],
                "cutting": cutting,
                "connect_from_previous": connected,
            }
        )
    return {
        "id": f"grid_{index:04d}",
        "split": "evaluation",
        "purpose": "密集适用域内原始质量失败筛选候选",
        "initial_surface": {
            "kind": "plane",
            "height_coefficients": [a, b, 0.0],
        },
        "plan": {
            "center_xy_mm": [0.0, 0.0],
            "allowed_radius_mm": 3.0,
        },
        "tool": {
            "kind": "sphere",
            "radius_mm": radius,
        },
        "events": events,
    }


def screen(document):
    policy = document["replay_policy"]
    dense_axis = np.linspace(-2.0, 2.0, 161)
    dense_xy = np.stack(
        np.meshgrid(dense_axis, dense_axis, indexing="ij"),
        axis=-1,
    )
    selected = {}
    raw_failure_count = 0
    dense_scope_failure_count = 0
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
        dense_scope_failure_count += 1
        if index in EXCLUDED_INDICES:
            continue
        slope = values[0]
        ranking = (quality["bad_faces"], -index)
        if slope not in selected or ranking > selected[slope]["ranking"]:
            selected[slope] = {
                "ranking": ranking,
                "generation_index": index,
                "parameters": values,
                "quality": quality,
                "case": case,
            }
    return {
        "screened_case_count": (
            len(PLANE_A)
            * len(PLANE_B)
            * len(RADII)
            * len(SHIFTS)
            * len(Z_DELTAS)
        ),
        "raw_failure_count": raw_failure_count,
        "dense_scope_raw_failure_count": dense_scope_failure_count,
        "selected": [selected[slope] for slope in PLANE_A],
    }


def verify(result, document):
    screening = document["screening"]
    assert result["screened_case_count"] == screening["screened_case_count"]
    assert result["raw_failure_count"] == screening["raw_failure_count"]
    assert (
        result["dense_scope_raw_failure_count"]
        == screening["dense_scope_raw_failure_count"]
    )
    selected_indices = [row["generation_index"] for row in result["selected"]]
    assert selected_indices == screening["selected_generation_indices"]
    for generated, frozen in zip(result["selected"], document["cases"]):
        expected = frozen["expected_raw_quality"]
        quality = generated["quality"]
        assert quality["bad_faces"] == expected["bad_faces"]
        assert abs(quality["min_q"] - expected["min_q"]) <= 1e-12
        assert (
            abs(quality["min_angle_deg"] - expected["min_angle_deg"])
            <= 1e-12
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--verify",
        type=Path,
        default=HERE / "quality_failure_cases_v2.json",
    )
    args = parser.parse_args()
    document = load_document(args.verify)
    result = screen(document)
    verify(result, document)
    summary = {
        key: value for key, value in result.items() if key != "selected"
    }
    summary["selected_generation_indices"] = [
        row["generation_index"] for row in result["selected"]
    ]
    summary["selected_raw_bad_faces"] = [
        row["quality"]["bad_faces"] for row in result["selected"]
    ]
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
