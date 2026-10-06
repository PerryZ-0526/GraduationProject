"""运行共同试题、受限旧方法回归和最小接缝方法对照。"""
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import hashlib
import json
import sys
from time import perf_counter

import numpy as np

from motion_record import (
    actual_material_field,
    classify_points,
    load_document,
    replay_case,
    sample_box,
)
from geogram_baseline import geogram_surface


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "局部区域重建阶段一"))
from patch_model import PatchModel, Rejected as PatchRejected, Sweep

sys.path.insert(0, str(HERE.parent / "计划裁剪特征重建"))
from clipped_patch import audit_candidate, generate

from surface_methods import (
    height_surface,
    implicit_contour_surface,
    maintain_surface,
    mesh_quality,
    mesh_topology,
    sampled_surface_audit,
    source_fitted_height_surface,
)
from state_metrics import planned_state_metrics


def source_hashes():
    paths = [
        HERE / "cases.json",
        HERE / "method_evaluation_cases.json",
        HERE / "quality_failure_cases.json",
        HERE / "quality_failure_cases_v2.json",
        HERE / "screen_quality_failure_cases.py",
        HERE / "geogram_baseline.py",
        HERE / "geogram_boolean.cpp",
        HERE / "build_geogram_baseline.sh",
        HERE / "motion_record.py",
        HERE / "state_metrics.py",
        HERE / "surface_methods.py",
        HERE / "test_motion_record.py",
        HERE / "experiment.py",
        HERE.parent / "局部区域重建阶段一" / "patch_model.py",
        HERE.parent / "计划裁剪特征重建" / "clipped_patch.py",
    ]
    return {
        str(path.relative_to(HERE.parents[1])): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in paths
    }


def save_candidate(path, candidate):
    names = sorted(candidate.feature_rings)
    rings = [np.asarray(candidate.feature_rings[name], dtype=np.int64) for name in names]
    np.savez(
        path,
        vertices=np.asarray(candidate.mesh.vertices, dtype=np.float64),
        faces=np.asarray(candidate.mesh.faces, dtype=np.int64),
        face_sources=np.asarray(candidate.face_sources, dtype=np.str_),
        feature_names=np.asarray(names, dtype=np.str_),
        feature_ring_vertices=np.concatenate(rings) if rings else np.empty(0, dtype=np.int64),
        feature_ring_offsets=np.cumsum([0, *map(len, rings)], dtype=np.int64),
    )


def fixed_answer_result(case, replay):
    expected = case["expected"]
    probes = [item["point_mm"] for item in expected["point_states"]]
    states = classify_points(probes, case, replay).tolist()
    checks = {
        "accepted_events": replay["accepted_event_ids"] == expected["accepted_event_ids"],
        "late_events": replay["late_event_ids"] == expected["late_event_ids"],
        "primitive_count": len(replay["primitives"]) == expected["primitive_count"],
        "connected_segment_count": (
            replay["connected_segment_count"] == expected["connected_segment_count"]
        ),
        "point_states": states == [item["state"] for item in expected["point_states"]],
    }
    result = {
        "case_id": case["id"],
        "split": case["split"],
        "purpose": case["purpose"],
        "accepted_event_ids": replay["accepted_event_ids"],
        "late_event_ids": replay["late_event_ids"],
        "primitive_count": len(replay["primitives"]),
        "connected_segment_count": replay["connected_segment_count"],
        "point_states": [
            {**spec, "actual_state": state}
            for spec, state in zip(expected["point_states"], states)
        ],
        "checks": checks,
    }
    if "state_metrics" in expected:
        actual_metrics = planned_state_metrics(case, replay)
        expected_metrics = expected["state_metrics"]
        tolerance = expected_metrics["absolute_tolerance_mm3"]
        metric_checks = {
            key: abs(actual_metrics[key] - expected_metrics[key]) <= tolerance
            for key in [
                "planned_removal_volume_mm3",
                "achieved_within_plan_volume_mm3",
                "remaining_within_plan_volume_mm3",
                "overcut_within_plan_volume_mm3",
                "outside_plan_removed_volume_mm3",
                "actual_removed_volume_mm3",
                "completion_fraction",
            ]
        }
        checks["state_metrics"] = all(metric_checks.values())
        result["state_metrics"] = {
            "actual": actual_metrics,
            "expected": expected_metrics,
            "checks": metric_checks,
        }
    result["passed"] = all(checks.values())
    return result


def invariants(document, cases):
    policy = document["replay_policy"]
    repeat = cases["repeat_same_path"]
    before_id, after_id = repeat["expected"]["prefix_equivalent"]
    before = replay_case(repeat, policy, before_id)
    after = replay_case(repeat, policy, after_id)
    repeat_points = sample_box(repeat)
    repeat_delta = float(
        np.max(
            np.abs(
                actual_material_field(repeat_points, repeat, before)
                - actual_material_field(repeat_points, repeat, after)
            ),
            initial=0.0,
        )
    )

    crossing = cases["tilted_crossing_paths"]
    crossing_replay = replay_case(crossing, policy)
    reversed_replay = dict(
        crossing_replay,
        primitives=list(reversed(crossing_replay["primitives"])),
    )
    crossing_points = sample_box(crossing)
    order_delta = float(
        np.max(
            np.abs(
                actual_material_field(crossing_points, crossing, crossing_replay)
                - actual_material_field(crossing_points, crossing, reversed_replay)
            ),
            initial=0.0,
        )
    )
    return {
        "repeat_path_max_delta_mm": repeat_delta,
        "repeat_path_pass": repeat_delta <= 2e-15,
        "crossing_order_max_delta_mm": order_delta,
        "crossing_order_pass": order_delta == 0.0,
        "probe_grid_role": "只验证集合不变量，不作为曲面误差证书",
    }


def run_height_map(case, replay):
    model = PatchModel(spacing=0.2, kind="plane", samples=32, half_width=4.0)
    rows = []
    for primitive in replay["primitives"]:
        tool = Sweep(
            tuple(primitive["start"][:2]),
            tuple(primitive["end"][:2]),
            primitive["radius"],
            float(primitive["end"][2]),
        )
        try:
            row = dict(model.update(tool))
        except PatchRejected:
            row = dict(model.attempts[-1])
        rows.append(row)
        if not row["accepted"]:
            break
    common_residual = float(
        np.max(
            np.abs(actual_material_field(model.vertices, case, replay)),
            initial=0.0,
        )
    )
    return {
        "case_id": case["id"],
        "method": "既有固定底网高度更新",
        "scope": "仅支持单值表面和水平等高球心运动",
        "accepted_steps": sum(row["accepted"] for row in rows),
        "attempted_steps": len(rows),
        "rows": rows,
        "common_boundary_residual_max_mm": common_residual,
        "passed": (
            len(rows) == len(replay["primitives"])
            and all(row["accepted"] for row in rows)
            and common_residual <= 1e-12
        ),
    }, model.vertices.copy()


def seam_comparison(case, output):
    center_z = min(event["position_mm"][2] for event in case["events"])
    arguments = {
        "center_z": center_z,
        "tool_radius": case["tool"]["radius_mm"],
        "clip_radius": case["plan"]["allowed_radius_mm"],
        "outer_radius": 3.0,
        "spacing": 0.25,
    }
    methods = {}
    for name, preserve in [
        ("all_seams", True),
        ("source_aware", False),
    ]:
        candidate = generate(**arguments, preserve_smooth_seam=preserve)
        audit = audit_candidate(candidate)
        mesh_name = f"vertical_{name}.npz"
        save_candidate(output / mesh_name, candidate)
        methods[name] = {
            "mesh": mesh_name,
            "preserve_smooth_seam": preserve,
            "audit": audit,
        }
    all_seams = methods["all_seams"]["audit"]
    source_aware = methods["source_aware"]["audit"]
    same_error_budget = (
        max(
            all_seams["mesh_to_target_upper_mm"],
            all_seams["target_to_mesh_upper_mm"],
            source_aware["mesh_to_target_upper_mm"],
            source_aware["target_to_mesh_upper_mm"],
        )
        <= 0.1
        and abs(
            all_seams["target_to_mesh_upper_mm"]
            - source_aware["target_to_mesh_upper_mm"]
        )
        < 1e-5
    )
    expected = {
        "all_seams_shape_rejected": (
            not all_seams["accepted"] and "shape_quality" in all_seams["reasons"]
        ),
        "source_aware_accepted": source_aware["accepted"],
        "same_error_budget": same_error_budget,
    }
    return {
        "case_id": case["id"],
        "input": arguments,
        "methods": methods,
        "checks": expected,
        "passed": all(expected.values()),
        "conclusion_scope": (
            "只支持解析平面上的同轴竖直近转折案例；"
            "证明该案例中不强制C1接缝可消除薄带差面，不证明一般三维方法优势"
        ),
    }


def crossing_comparison(case, replay, output, parameter_policy):
    """同一倾斜输入上的解析候选、固定维护和普通等值面比较。"""
    xy_bounds = (-2.0, 2.0, -2.0, 2.0)
    z_bounds = (-0.9, 0.9)
    spacing = parameter_policy["candidate_xy_spacing_mm"]
    dense_target_spacing = 0.025
    prefix = case["id"]

    target, target_diagnostics = height_surface(
        case,
        replay,
        xy_bounds,
        dense_target_spacing,
    )
    target_name = f"{prefix}_dense_target.vtp"
    target.save(output / target_name)

    started = perf_counter()
    raw_candidate, candidate_diagnostics = height_surface(
        case,
        replay,
        xy_bounds,
        spacing,
    )
    candidate_elapsed_ms = (perf_counter() - started) * 1000.0
    started = perf_counter()
    source_fitted_candidate, source_fitted_diagnostics = (
        source_fitted_height_surface(
            case,
            replay,
            xy_bounds,
            spacing,
        )
    )
    source_fitted_elapsed_ms = (perf_counter() - started) * 1000.0
    maintained_candidate, maintenance_diagnostics = maintain_surface(
        raw_candidate,
        target_length=parameter_policy["maintenance_target_length_mm"],
        iterations=parameter_policy["maintenance_iterations"],
        feature_angle_deg=parameter_policy["maintenance_feature_angle_deg"],
        surface_budget=parameter_policy["maintenance_surface_budget_mm"],
    )
    baseline, baseline_diagnostics = implicit_contour_surface(
        case,
        replay,
        xy_bounds,
        z_bounds,
        spacing,
    )
    geogram_candidate, geogram_diagnostics = geogram_surface(
        case,
        replay,
        xy_bounds,
        z_bounds,
        spacing,
        output / f"{prefix}_geogram_work",
    )
    mesh_names = {
        "analytic_height_raw": f"{prefix}_height_raw.vtp",
        "analytic_height_source_fitted": f"{prefix}_height_source_fitted.vtp",
        "analytic_height_maintained": f"{prefix}_height_maintained.vtp",
        "implicit_contour_baseline": f"{prefix}_implicit_contour.vtp",
        "geogram_exact_csg": f"{prefix}_geogram_exact_csg.vtp",
    }
    raw_candidate.save(output / mesh_names["analytic_height_raw"])
    source_fitted_candidate.save(
        output / mesh_names["analytic_height_source_fitted"]
    )
    maintained_candidate.save(output / mesh_names["analytic_height_maintained"])
    baseline.save(output / mesh_names["implicit_contour_baseline"])
    geogram_candidate.save(output / mesh_names["geogram_exact_csg"])

    methods = {}
    for name, role, scope, mesh, elapsed_ms, diagnostics in [
        (
            "analytic_height_raw",
            "解析单值候选的生成消融",
            (
                "仅在每条竖线上的实际去除区间都与外表面连通、"
                "剩余外表面可写为单值高度时适用；未做质量维护"
            ),
            raw_candidate,
            candidate_elapsed_ms,
            candidate_diagnostics,
        ),
        (
            "analytic_height_source_fitted",
            "来源切换线约束与局部质量生成候选",
            (
                "仅在原始候选质量失败单元内对齐连续来源切换线，"
                "并沿三维长方向局部细分；不改动原本通过的单元"
            ),
            source_fitted_candidate,
            source_fitted_elapsed_ms,
            source_fitted_diagnostics,
        ),
        (
            "analytic_height_maintained",
            "受限候选方法加项目既有各向同性质量维护",
            (
                "解析单值候选生成后，使用开发案例固定的PyMeshLab参数维护；"
                "不支持内部空腔或非单值拓扑"
            ),
            maintained_candidate,
            candidate_elapsed_ms + maintenance_diagnostics["elapsed_ms"],
            {
                "generation": candidate_diagnostics,
                "maintenance": maintenance_diagnostics,
                "all_removed_intervals_top_connected": candidate_diagnostics[
                    "all_removed_intervals_top_connected"
                ],
            },
        ),
        (
            "implicit_contour_baseline",
            "项目既有普通工程基线，非作者强基线",
            "规则三维体素采样加VTK等值面提取",
            baseline,
            baseline_diagnostics["elapsed_ms"],
            baseline_diagnostics,
        ),
        (
            "geogram_exact_csg",
            "正式竞争性几何布尔基线",
            (
                "TOG 2025作者Geogram默认精确网格CSG；输入工具为"
                "固定subdivisions=3的离散胶囊，结果不附加质量维护"
            ),
            geogram_candidate,
            geogram_diagnostics["elapsed_ms"],
            geogram_diagnostics,
        ),
    ]:
        quality = mesh_quality(mesh)
        topology = mesh_topology(mesh)
        audit = sampled_surface_audit(mesh, target, case, replay)
        failure_reasons = []
        if quality["bad_faces"]:
            failure_reasons.append("shape_quality")
        if audit["implicit_residual"]["max_mm"] > 0.1:
            failure_reasons.append("sampled_geometry")
        if (
            name.startswith("analytic_height")
            and not diagnostics["all_removed_intervals_top_connected"]
        ):
            failure_reasons.append("outside_single_value_scope")
        if (
            name == "analytic_height_source_fitted"
            and not diagnostics["source_transition_continuous"]
        ):
            failure_reasons.append("discontinuous_source_transition")
        if (
            topology["connected_components"] != 1
            or topology["non_manifold_edges"]
            or topology["inconsistent_interior_edges"]
            or topology["self_intersection_faces"]
        ):
            failure_reasons.append("topology")
        if (
            name == "geogram_exact_csg"
            and (
                not diagnostics["full_solid_watertight"]
                or not diagnostics["full_solid_winding_consistent"]
            )
        ):
            failure_reasons.append("full_solid_topology")
        methods[name] = {
            "role": role,
            "scope": scope,
            "mesh": mesh_names[name],
            "elapsed_ms": elapsed_ms,
            "diagnostics": diagnostics,
            "quality": quality,
            "topology": topology,
            "sampled_surface_audit": audit,
            "failure_reasons": failure_reasons,
            "accepted_for_this_case": not failure_reasons,
        }

    raw_row = methods["analytic_height_raw"]
    source_fitted_row = methods["analytic_height_source_fitted"]
    candidate_row = methods["analytic_height_maintained"]
    baseline_row = methods["implicit_contour_baseline"]
    geogram_row = methods["geogram_exact_csg"]
    checks = {
        "dense_target_scope_valid": target_diagnostics[
            "all_removed_intervals_top_connected"
        ],
        "candidate_scope_valid": candidate_diagnostics[
            "all_removed_intervals_top_connected"
        ],
        "candidate_mesh_nonempty": (
            maintained_candidate.n_points > 0 and maintained_candidate.n_cells > 0
        ),
        "source_fitted_mesh_nonempty": (
            source_fitted_candidate.n_points > 0
            and source_fitted_candidate.n_cells > 0
        ),
        "baseline_mesh_nonempty": baseline.n_points > 0 and baseline.n_cells > 0,
        "geogram_mesh_nonempty": (
            geogram_candidate.n_points > 0 and geogram_candidate.n_cells > 0
        ),
        "geogram_full_solid_valid": (
            geogram_diagnostics["full_solid_watertight"]
            and geogram_diagnostics["full_solid_winding_consistent"]
        ),
    }
    return {
        "case_id": case["id"],
        "input": {
            "xy_bounds_mm": list(xy_bounds),
            "z_bounds_mm": list(z_bounds),
            "method_spacing_mm": spacing,
            "dense_target_spacing_mm": dense_target_spacing,
            "primitive_count": len(replay["primitives"]),
            "parameter_policy": parameter_policy,
        },
        "common_target": {
            "kind": "解析倾斜平面减实际胶囊运动后的外表面下包络",
            "mesh": target_name,
            "diagnostics": target_diagnostics,
            "warning": "密集目标网格只用于抽样近邻测量，不是严格误差证书",
        },
        "methods": methods,
        "observed_comparison": {
            "maintenance_reduced_raw_bad_faces": (
                candidate_row["quality"]["bad_faces"] < raw_row["quality"]["bad_faces"]
            ),
            "source_fitting_reduced_raw_bad_faces": (
                source_fitted_row["quality"]["bad_faces"]
                < raw_row["quality"]["bad_faces"]
            ),
            "source_fitting_did_not_move_passing_grid": (
                raw_row["quality"]["bad_faces"] > 0
                or (
                    source_fitted_row["diagnostics"]["snapped_vertex_count"] == 0
                    and source_fitted_row["diagnostics"][
                        "inserted_midpoint_count"
                    ]
                    == 0
                )
            ),
            "maintained_candidate_bad_faces_not_more_than_baseline": (
                candidate_row["quality"]["bad_faces"]
                <= baseline_row["quality"]["bad_faces"]
            ),
            "maintained_candidate_sampled_max_not_more_than_baseline": (
                candidate_row["sampled_surface_audit"]["dense_target_to_mesh"][
                    "max_mm"
                ]
                <= baseline_row["sampled_surface_audit"]["dense_target_to_mesh"][
                    "max_mm"
                ]
            ),
            "maintained_candidate_faster_in_this_run": (
                candidate_row["elapsed_ms"] < baseline_row["elapsed_ms"]
            ),
            "source_fitted_has_fewer_bad_faces_than_geogram": (
                source_fitted_row["quality"]["bad_faces"]
                < geogram_row["quality"]["bad_faces"]
            ),
        },
        "checks": checks,
        "passed": all(checks.values()),
        "conclusion_scope": (
            "这是解析倾斜输入上的受限候选、既有质量维护、普通工程"
            "基线和Geogram精确网格CSG比较；Geogram承担几何布尔角色，"
            "其离散工具与未维护输出不代表质量优化方法；结果不外推到"
            "真实骨面、内部空腔或一般非单值拓扑"
        ),
    }


def main():
    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    output = HERE / "实验结果" / now.strftime("%Y%m%d_%H%M%S")
    output.mkdir(parents=True)
    document = load_document()
    evaluation_document = load_document(HERE / "method_evaluation_cases.json")
    challenge_document = load_document(HERE / "quality_failure_cases_v2.json")
    cases = {case["id"]: case for case in document["cases"]}
    policy = document["replay_policy"]
    parameter_policy = evaluation_document["parameter_policy"]
    challenge_parameter_policy = {
        **parameter_policy,
        **challenge_document["parameter_policy"],
    }
    result = {
        "schema_version": 1,
        "time_beijing": now.strftime("%Y-%m-%d %H:%M:%S"),
        "status": "running",
        "scope": (
            "第一批共同仿真运动记录与固定答案；"
            "第二批包含解析竖直接缝消融，以及倾斜开发案例和"
            "三条冻结评测路线上的受限候选、来源切换线局部生成、"
            "固定质量维护、普通工程基线与Geogram正式几何基线；"
            "第三批增加四条在来源修复运行前冻结的原始质量失败路线；"
            "另含四例计划体积状态固定答案"
        ),
        "record_kind": document["record_kind"],
        "coordinate_frame": document["coordinate_frame"],
        "replay_policy": policy,
        "source_sha256": source_hashes(),
        "baseline_registry": document["baselines"],
        "case_results": [],
    }

    def save():
        (output / "results.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    save()
    try:
        replays = {}
        for case in document["cases"]:
            replay = replay_case(case, policy)
            replays[case["id"]] = replay
            row = fixed_answer_result(case, replay)
            result["case_results"].append(row)
            print(case["id"], row["passed"], flush=True)

        result["invariants"] = invariants(document, cases)
        height_rows = []
        height_vertices = {}
        for case_id in ["shallow_milling", "repeat_same_path"]:
            row, vertices = run_height_map(cases[case_id], replays[case_id])
            height_rows.append(row)
            height_vertices[case_id] = vertices
        repeat_mesh_delta = float(
            np.max(
                np.abs(
                    height_vertices["shallow_milling"]
                    - height_vertices["repeat_same_path"]
                ),
                initial=0.0,
            )
        )
        result["restricted_height_map"] = {
            "runs": height_rows,
            "repeat_vs_single_max_vertex_delta_mm": repeat_mesh_delta,
            "repeat_invariant_pass": repeat_mesh_delta <= 2e-15,
            "unsupported_cases": [
                "plan_edge_overcut",
                "vertical_depth_transition",
                "tilted_crossing_paths",
                "stop_gap_and_late_event",
            ],
            "unsupported_is_not_failure_or_success": True,
        }
        result["seam_comparison"] = seam_comparison(
            cases["vertical_depth_transition"],
            output,
        )
        result["crossing_comparison"] = crossing_comparison(
            cases["tilted_crossing_paths"],
            replays["tilted_crossing_paths"],
            output,
            parameter_policy,
        )
        evaluation_rows = []
        for case in evaluation_document["cases"]:
            replay = replay_case(case, evaluation_document["replay_policy"])
            row = crossing_comparison(
                case,
                replay,
                output,
                parameter_policy,
            )
            if "repeat_equivalent_event_ids" in case:
                before_id, after_id = case["repeat_equivalent_event_ids"]
                before = replay_case(
                    case,
                    evaluation_document["replay_policy"],
                    before_id,
                )
                after = replay_case(
                    case,
                    evaluation_document["replay_policy"],
                    after_id,
                )
                points = sample_box(case)
                row["repeat_path_max_field_delta_mm"] = float(
                    np.max(
                        np.abs(
                            actual_material_field(points, case, before)
                            - actual_material_field(points, case, after)
                        ),
                        initial=0.0,
                    )
                )
                row["repeat_path_invariant_pass"] = (
                    row["repeat_path_max_field_delta_mm"] <= 2e-15
                )
            evaluation_rows.append(row)
            print(case["id"], row["passed"], flush=True)
        result["surface_method_evaluation"] = {
            "frozen_before_first_run": evaluation_document[
                "frozen_before_first_run"
            ],
            "parameter_policy": parameter_policy,
            "cases": evaluation_rows,
            "all_experiments_completed": all(row["passed"] for row in evaluation_rows),
            "raw_candidate_accepted": sum(
                row["methods"]["analytic_height_raw"]["accepted_for_this_case"]
                for row in evaluation_rows
            ),
            "source_fitted_candidate_accepted": sum(
                row["methods"]["analytic_height_source_fitted"][
                    "accepted_for_this_case"
                ]
                for row in evaluation_rows
            ),
            "maintained_candidate_accepted": sum(
                row["methods"]["analytic_height_maintained"][
                    "accepted_for_this_case"
                ]
                for row in evaluation_rows
            ),
            "implicit_baseline_accepted": sum(
                row["methods"]["implicit_contour_baseline"][
                    "accepted_for_this_case"
                ]
                for row in evaluation_rows
            ),
            "geogram_baseline_completed": sum(
                "geogram_exact_csg" in row["methods"]
                for row in evaluation_rows
            ),
            "geogram_baseline_accepted": sum(
                row["methods"]["geogram_exact_csg"]["accepted_for_this_case"]
                for row in evaluation_rows
            ),
            "unconditional_maintenance_regressions": sum(
                row["methods"]["analytic_height_raw"]["accepted_for_this_case"]
                and not row["methods"]["analytic_height_maintained"][
                    "accepted_for_this_case"
                ]
                for row in evaluation_rows
            ),
            "recommended_policy": (
                "原始解析候选通过时不改动；仅对质量失败单元启用"
                "来源切换线对齐和局部质量生成，复核几何与拓扑后发布。"
                "固定各向同性维护在冻结评测中引入自交，仍不得自动回灌"
            ),
        }
        challenge_rows = []
        for case in challenge_document["cases"]:
            replay = replay_case(case, challenge_document["replay_policy"])
            row = crossing_comparison(
                case,
                replay,
                output,
                challenge_parameter_policy,
            )
            expected = case["expected_raw_quality"]
            actual = row["methods"]["analytic_height_raw"]
            raw_checks = {
                "vertices": actual["quality"]["vertices"] == expected["vertices"],
                "faces": actual["quality"]["faces"] == expected["faces"],
                "bad_faces": (
                    actual["quality"]["bad_faces"] == expected["bad_faces"]
                ),
                "min_q": abs(actual["quality"]["min_q"] - expected["min_q"]) <= 1e-12,
                "min_angle_deg": (
                    abs(
                        actual["quality"]["min_angle_deg"]
                        - expected["min_angle_deg"]
                    )
                    <= 1e-12
                ),
                "all_removed_intervals_top_connected": (
                    actual["diagnostics"]["all_removed_intervals_top_connected"]
                    == expected["all_removed_intervals_top_connected"]
                ),
            }
            row["frozen_raw_checks"] = raw_checks
            row["passed"] = row["passed"] and all(raw_checks.values())
            challenge_rows.append(row)
            print(case["id"], row["passed"], flush=True)
        result["quality_failure_challenge"] = {
            "frozen_before_source_fitted_run": challenge_document[
                "frozen_before_source_fitted_run"
            ],
            "screening": challenge_document["screening"],
            "parameter_policy": challenge_parameter_policy,
            "cases": challenge_rows,
            "all_experiments_completed": all(row["passed"] for row in challenge_rows),
            "raw_failures_confirmed": sum(
                not row["methods"]["analytic_height_raw"]["accepted_for_this_case"]
                for row in challenge_rows
            ),
            "source_fitted_candidate_accepted": sum(
                row["methods"]["analytic_height_source_fitted"][
                    "accepted_for_this_case"
                ]
                for row in challenge_rows
            ),
            "source_transition_continuous": sum(
                row["methods"]["analytic_height_source_fitted"]["diagnostics"][
                    "source_transition_continuous"
                ]
                for row in challenge_rows
            ),
            "interpretation": (
                "挑战集只按原始候选失败筛选；来源修复首次运行后不回调"
                "输入或旧参数，未通过案例按负结果保留"
            ),
        }
        result["summary"] = {
            "fixed_cases_passed": sum(row["passed"] for row in result["case_results"]),
            "fixed_cases_total": len(result["case_results"]),
            "state_metric_cases_passed": sum(
                row["passed"] and "state_metrics" in row
                for row in result["case_results"]
            ),
            "state_metric_cases_total": sum(
                "state_metrics" in row for row in result["case_results"]
            ),
            "invariants_passed": all(
                value
                for key, value in result["invariants"].items()
                if key.endswith("_pass")
            ),
            "restricted_height_map_passed": (
                all(row["passed"] for row in height_rows)
                and result["restricted_height_map"]["repeat_invariant_pass"]
            ),
            "seam_comparison_passed": result["seam_comparison"]["passed"],
            "crossing_comparison_completed": result["crossing_comparison"]["passed"],
            "heldout_surface_cases_completed": result[
                "surface_method_evaluation"
            ]["all_experiments_completed"],
            "heldout_raw_candidate_accepted": result["surface_method_evaluation"][
                "raw_candidate_accepted"
            ],
            "heldout_source_fitted_candidate_accepted": result[
                "surface_method_evaluation"
            ]["source_fitted_candidate_accepted"],
            "heldout_maintained_candidate_accepted": result[
                "surface_method_evaluation"
            ][
                "maintained_candidate_accepted"
            ],
            "heldout_candidate_total": len(evaluation_rows),
            "quality_failure_challenge_completed": result[
                "quality_failure_challenge"
            ]["all_experiments_completed"],
            "quality_failure_raw_confirmed": result[
                "quality_failure_challenge"
            ]["raw_failures_confirmed"],
            "quality_failure_source_fitted_accepted": result[
                "quality_failure_challenge"
            ]["source_fitted_candidate_accepted"],
            "quality_failure_challenge_total": len(challenge_rows),
            "engineering_baseline_completed": True,
            "competitive_baseline_completed": (
                result["surface_method_evaluation"][
                    "geogram_baseline_completed"
                ]
                == len(evaluation_rows)
            ),
            "real_motion_record_used": False,
            "real_bone_updated": False,
        }
        result["status"] = (
            "completed"
            if (
                result["summary"]["fixed_cases_passed"]
                == result["summary"]["fixed_cases_total"]
                and result["summary"]["invariants_passed"]
                and result["summary"]["restricted_height_map_passed"]
                and result["summary"]["seam_comparison_passed"]
                and result["summary"]["crossing_comparison_completed"]
                and result["summary"]["heldout_surface_cases_completed"]
                and result["summary"]["quality_failure_challenge_completed"]
            )
            else "completed_with_unexpected_results"
        )
    finally:
        save()
    print(output)


if __name__ == "__main__":
    main()
