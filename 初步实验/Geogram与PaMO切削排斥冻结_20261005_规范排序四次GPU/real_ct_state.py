"""将既有真实CT局部序列映射为计划状态和保守误差区间。"""
from datetime import datetime
import hashlib
import importlib.util
import json
from pathlib import Path

import matplotlib.tri as mtri
import numpy as np


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DEMO = ROOT / "初步实验/真实骨模型演示"
JOINT = ROOT / "初步实验/边界过渡带联合重建/实验结果/joint.npz"
SEQUENCE = (
    ROOT
    / "初步实验/局部适用域与核显计算/实验结果/local_1.8.npz"
)
SEQUENCE_RECORD = (
    ROOT
    / "初步实验/局部适用域与核显计算/实验结果/comparison.json"
)
SCENARIOS = HERE / "real_ct_uncertainty_scenarios_v2.json"


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_plan_module():
    spec = importlib.util.spec_from_file_location(
        "real_ct_plan_definition",
        DEMO / "real_bone_demo.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TriangulatedHeight:
    """固定XY三角剖分上的分片线性高度查询。"""

    def __init__(self, xy, faces):
        self.xy = np.asarray(xy, dtype=np.float64)
        self.faces = np.asarray(faces, dtype=np.int64)
        triangulation = mtri.Triangulation(
            self.xy[:, 0],
            self.xy[:, 1],
            self.faces,
        )
        self.finder = triangulation.get_trifinder()
        triangle_xy = self.xy[self.faces]
        self.basis = triangle_xy[:, 1:] - triangle_xy[:, :1]

    def query(self, z, xy):
        z = np.asarray(z, dtype=np.float64)
        xy = np.asarray(xy, dtype=np.float64)
        triangle_z = z[self.faces]
        right_hand_side = triangle_z[:, 1:] - triangle_z[:, :1]
        gradient = np.linalg.solve(
            self.basis,
            right_hand_side[..., None],
        )[..., 0]
        intercept = (
            triangle_z[:, 0]
            - np.sum(gradient * self.xy[self.faces[:, 0]], axis=1)
        )
        face_ids = self.finder(xy[:, 0], xy[:, 1])
        if np.any(face_ids < 0):
            raise ValueError("积分点超出已验证真实CT局部图域")
        return (
            np.sum(gradient[face_ids] * xy, axis=1)
            + intercept[face_ids]
        )


def plan_samples(radial_intervals, radial_order, angular_samples):
    """在计划深度跳变半径处分段的极坐标Gauss-Legendre积分点。"""
    roots, root_weights = np.polynomial.legendre.leggauss(radial_order)
    theta = (
        np.arange(angular_samples, dtype=np.float64) + 0.5
    ) * (2.0 * np.pi / angular_samples)
    direction = np.column_stack((np.cos(theta), np.sin(theta)))
    points = []
    weights = []
    band_ids = []
    for band, (lower, upper) in enumerate(radial_intervals):
        radius = (roots + 1.0) * (upper - lower) / 2.0 + lower
        radial_weights = root_weights * (upper - lower) / 2.0
        points.append((radius[:, None, None] * direction[None, :, :]).reshape(-1, 2))
        weights.append(
            (
                radial_weights[:, None]
                * radius[:, None]
                * (2.0 * np.pi / angular_samples)
                * np.ones((1, angular_samples))
            ).reshape(-1)
        )
        band_ids.append(
            np.full(radial_order * angular_samples, band, dtype=np.int8)
        )
    return (
        np.vstack(points),
        np.concatenate(weights),
        np.concatenate(band_ids),
    )


def target_height(band_ids, plan):
    values = np.array([plan.D_POST, plan.D_BOSS, 0.0], dtype=np.float64)
    return values[np.asarray(band_ids, dtype=np.int64)]


def integrate(values, weights):
    return float(np.sum(np.asarray(values, dtype=np.float64) * weights))


def nominal_state(initial_z, current_z, target_z, weights):
    planned = np.maximum(initial_z - target_z, 0.0)
    actual = np.maximum(initial_z - current_z, 0.0)
    achieved = np.minimum(actual, planned)
    remaining = planned - achieved
    overcut = np.maximum(actual - planned, 0.0)
    planned_volume = integrate(planned, weights)
    achieved_volume = integrate(achieved, weights)
    return {
        "planned_removal_volume_mm3": planned_volume,
        "actual_removed_volume_mm3": integrate(actual, weights),
        "achieved_within_plan_volume_mm3": achieved_volume,
        "remaining_within_plan_volume_mm3": integrate(remaining, weights),
        "overcut_within_plan_volume_mm3": integrate(overcut, weights),
        "completion_fraction": (
            achieved_volume / planned_volume if planned_volume else 0.0
        ),
        "remaining_area_mm2": integrate(remaining > 0.0, weights),
        "overcut_area_mm2": integrate(overcut > 0.0, weights),
    }


class RealCtStateMapper:
    """把验收后的固定XY局部网格映射为同版本计划状态。"""

    def __init__(
        self,
        initial_vertices,
        faces,
        plan=None,
        config=None,
        radial_order=None,
        angular_samples=None,
    ):
        self.plan = load_plan_module() if plan is None else plan
        self.config = (
            json.loads(SCENARIOS.read_text(encoding="utf-8"))
            if config is None
            else config
        )
        quadrature = self.config["quadrature"]
        self.xy, self.weights, self.band_ids = plan_samples(
            quadrature["radial_intervals_mm"],
            radial_order or quadrature["radial_order"],
            angular_samples or quadrature["angular_samples"],
        )
        self.target_z = target_height(self.band_ids, self.plan)
        initial_vertices = np.asarray(initial_vertices, dtype=np.float64)
        self.query = TriangulatedHeight(initial_vertices[:, :2], faces)
        self.initial_z = self.query.query(initial_vertices[:, 2], self.xy)
        self.algorithm_scenario = next(
            scenario for scenario in self.config["scenarios"]
            if scenario["id"] == "algorithm_bound_only"
        )

    def nominal(self, vertices):
        current_z = self.query.query(
            np.asarray(vertices, dtype=np.float64)[:, 2],
            self.xy,
        )
        return nominal_state(
            self.initial_z,
            current_z,
            self.target_z,
            self.weights,
        )

    def algorithm_interval(self, vertices, algorithm_bound_mm):
        current_z = self.query.query(
            np.asarray(vertices, dtype=np.float64)[:, 2],
            self.xy,
        )
        return uncertain_state(
            self.initial_z,
            current_z,
            self.target_z,
            self.xy,
            self.weights,
            self.algorithm_scenario,
            algorithm_bound_mm,
        )

    def published_state(self, vertices, algorithm_bound_mm):
        current_z = self.query.query(
            np.asarray(vertices, dtype=np.float64)[:, 2],
            self.xy,
        )
        return {
            "nominal": nominal_state(
                self.initial_z,
                current_z,
                self.target_z,
                self.weights,
            ),
            "algorithm_bound_interval": uncertain_state(
                self.initial_z,
                current_z,
                self.target_z,
                self.xy,
                self.weights,
                self.algorithm_scenario,
                algorithm_bound_mm,
            ),
            "analysis_radius_mm": self.config["analysis_region"]["radius_mm"],
            "full_plan_boundary_included": self.config["analysis_region"][
                "includes_full_plan_boundary"
            ],
        }


def positional_error_bounds(xy, initial_z, current_z, target_z, scenario, algorithm):
    lever = np.maximum.reduce(
        (
            np.linalg.norm(np.column_stack((xy, initial_z)), axis=1),
            np.linalg.norm(np.column_stack((xy, current_z)), axis=1),
            np.linalg.norm(np.column_stack((xy, target_z)), axis=1),
        )
    )
    angle = np.radians(scenario["registration_rotation_deg"])
    registration = (
        scenario["registration_translation_mm"]
        + 2.0 * lever * np.sin(angle / 2.0)
    )
    latency = (
        scenario["max_tool_speed_mm_s"]
        * scenario["state_age_ms"]
        / 1000.0
    )
    planned_error = scenario["ct_surface_mm"] + registration
    actual_error = (
        scenario["ct_surface_mm"]
        + registration
        + scenario["tool_calibration_mm"]
        + scenario["tracking_mm"]
        + latency
        + algorithm
    )
    return planned_error, actual_error


def uncertain_state(
    initial_z,
    current_z,
    target_z,
    xy,
    weights,
    scenario,
    algorithm_bound_mm,
):
    planned = np.maximum(initial_z - target_z, 0.0)
    actual = np.maximum(initial_z - current_z, 0.0)
    planned_error, actual_error = positional_error_bounds(
        xy,
        initial_z,
        current_z,
        target_z,
        scenario,
        algorithm_bound_mm,
    )
    planned_lower = np.maximum(planned - planned_error, 0.0)
    planned_upper = planned + planned_error
    actual_lower = np.maximum(actual - actual_error, 0.0)
    actual_upper = actual + actual_error
    achieved_lower = np.minimum(actual_lower, planned_lower)
    achieved_upper = np.minimum(actual_upper, planned_upper)
    remaining_lower = np.maximum(planned_lower - actual_upper, 0.0)
    remaining_upper = np.maximum(planned_upper - actual_lower, 0.0)
    overcut_lower = np.maximum(actual_lower - planned_upper, 0.0)
    overcut_upper = np.maximum(actual_upper - planned_lower, 0.0)
    active = (planned_upper > 0.0) | (actual_upper > 0.0)
    progress_lower = planned_lower - actual_upper
    progress_upper = planned_upper - actual_lower
    uncertain = active & (progress_lower <= 0.0) & (progress_upper >= 0.0)

    planned_lower_volume = integrate(planned_lower, weights)
    planned_upper_volume = integrate(planned_upper, weights)
    achieved_lower_volume = integrate(achieved_lower, weights)
    achieved_upper_volume = integrate(achieved_upper, weights)
    return {
        "component_bounds_mm": {
            "planned_depth_error_min": float(np.min(planned_error)),
            "planned_depth_error_max": float(np.max(planned_error)),
            "actual_depth_error_min": float(np.min(actual_error)),
            "actual_depth_error_max": float(np.max(actual_error)),
            "latency_displacement": (
                scenario["max_tool_speed_mm_s"]
                * scenario["state_age_ms"]
                / 1000.0
            ),
            "algorithm_surface_bound": float(algorithm_bound_mm),
        },
        "planned_removal_volume_interval_mm3": [
            planned_lower_volume,
            planned_upper_volume,
        ],
        "actual_removed_volume_interval_mm3": [
            integrate(actual_lower, weights),
            integrate(actual_upper, weights),
        ],
        "achieved_within_plan_volume_interval_mm3": [
            achieved_lower_volume,
            achieved_upper_volume,
        ],
        "remaining_within_plan_volume_interval_mm3": [
            integrate(remaining_lower, weights),
            integrate(remaining_upper, weights),
        ],
        "overcut_within_plan_volume_interval_mm3": [
            integrate(overcut_lower, weights),
            integrate(overcut_upper, weights),
        ],
        "completion_fraction_interval": [
            (
                achieved_lower_volume / planned_upper_volume
                if planned_upper_volume
                else 0.0
            ),
            min(
                1.0,
                (
                    achieved_upper_volume / planned_lower_volume
                    if planned_lower_volume
                    else 1.0
                ),
            ),
        ],
        "uncertain_target_state_area_mm2": integrate(uncertain, weights),
        "definitely_remaining_area_mm2": integrate(
            active & (progress_lower > 0.0),
            weights,
        ),
        "definitely_overcut_area_mm2": integrate(
            active & (progress_upper < 0.0),
            weights,
        ),
    }


def evaluate_sequence(snapshot_data, plan, config, radial_order, angular_samples):
    snapshots = snapshot_data["snapshots"]
    mapper = RealCtStateMapper(
        snapshots[0],
        snapshot_data["faces"],
        plan=plan,
        config=config,
        radial_order=radial_order,
        angular_samples=angular_samples,
    )
    rows = []
    for step, vertices in enumerate(snapshots):
        rows.append(
            {
                "step": step,
                **mapper.nominal(vertices),
            }
        )
    current_z = mapper.query.query(snapshots[-1, :, 2], mapper.xy)
    return rows, (
        mapper.xy,
        mapper.weights,
        mapper.target_z,
        mapper.initial_z,
        current_z,
    )


def face_state_fields(
    snapshot_data,
    plan,
    scenarios,
    algorithm_bound_mm,
    analysis_radius_mm,
):
    snapshots = snapshot_data["snapshots"]
    faces = snapshot_data["faces"]
    initial = snapshots[0]
    current = snapshots[-1]
    xy = current[faces, :2].mean(axis=1)
    initial_z = initial[faces, 2].mean(axis=1)
    current_z = current[faces, 2].mean(axis=1)
    radius = np.linalg.norm(xy, axis=1)
    band_ids = np.where(radius < plan.R_POST, 0, np.where(radius < plan.R_BOSS, 1, 2))
    target_z = target_height(band_ids, plan)
    planned = np.maximum(initial_z - target_z, 0.0)
    actual = np.maximum(initial_z - current_z, 0.0)
    fields = {
        "face_centers_xy_mm": xy,
        "face_inside_analysis": radius <= analysis_radius_mm,
        "face_planned_depth_mm": planned,
        "face_actual_removed_mm": actual,
        "face_remaining_mm": np.maximum(planned - actual, 0.0),
        "face_overcut_mm": np.maximum(actual - planned, 0.0),
    }
    for scenario in scenarios:
        planned_error, actual_error = positional_error_bounds(
            xy,
            initial_z,
            current_z,
            target_z,
            scenario,
            algorithm_bound_mm,
        )
        planned_lower = np.maximum(planned - planned_error, 0.0)
        planned_upper = planned + planned_error
        actual_lower = np.maximum(actual - actual_error, 0.0)
        actual_upper = actual + actual_error
        remaining_lower = np.maximum(planned_lower - actual_upper, 0.0)
        remaining_upper = np.maximum(planned_upper - actual_lower, 0.0)
        overcut_lower = np.maximum(actual_lower - planned_upper, 0.0)
        overcut_upper = np.maximum(actual_upper - planned_lower, 0.0)
        status = np.full(len(faces), 0, dtype=np.int8)
        inside = fields["face_inside_analysis"]
        active = inside & ((planned_upper > 0.0) | (actual_upper > 0.0))
        status[active] = 3
        status[active & (remaining_lower > 0.0)] = 1
        status[active & (overcut_lower > 0.0)] = 2
        key = scenario["id"]
        fields[f"{key}_remaining_lower_mm"] = remaining_lower
        fields[f"{key}_remaining_upper_mm"] = remaining_upper
        fields[f"{key}_overcut_lower_mm"] = overcut_lower
        fields[f"{key}_overcut_upper_mm"] = overcut_upper
        fields[f"{key}_status_code"] = status
    fields["status_code_legend"] = np.array(
        [
            "outside_analysis_or_no_planned_change",
            "definitely_remaining",
            "definitely_overcut",
            "uncertain_target_state",
        ]
    )
    return fields


def run(output_root=None):
    config = json.loads(SCENARIOS.read_text(encoding="utf-8"))
    plan = load_plan_module()
    joint = np.load(JOINT)
    sequence = np.load(SEQUENCE)
    records = json.loads(SEQUENCE_RECORD.read_text(encoding="utf-8"))
    local_record = next(
        row for row in records["runs"]
        if row["method"] == "local" and row["z"] == 1.8
    )
    checks = {
        "initial_patch_matches_joint": bool(
            np.array_equal(sequence["snapshots"][0], joint["vertices"])
        ),
        "faces_match_joint": bool(np.array_equal(sequence["faces"], joint["faces"])),
        "xy_fixed_across_sequence": bool(
            np.array_equal(
                sequence["snapshots"][:, :, :2],
                np.broadcast_to(
                    sequence["snapshots"][0, :, :2],
                    sequence["snapshots"][:, :, :2].shape,
                ),
            )
        ),
        "sixteen_steps_accepted": local_record["accepted"] == 16,
        "seventeen_snapshots_present": len(sequence["snapshots"]) == 17,
        "analysis_inside_full_plan": (
            config["analysis_region"]["radius_mm"] < plan.R_PLATE
        ),
        "analysis_radius_matches_quadrature": (
            config["quadrature"]["radial_intervals_mm"][-1][1]
            == config["analysis_region"]["radius_mm"]
        ),
        "full_plan_radius_matches_source": (
            config["analysis_region"]["full_plan_radius_mm"] == plan.R_PLATE
        ),
    }
    if not all(checks.values()):
        raise RuntimeError(f"真实CT状态输入前置检查失败: {checks}")

    quadrature = config["quadrature"]
    rows, arrays = evaluate_sequence(
        sequence,
        plan,
        config,
        quadrature["radial_order"],
        quadrature["angular_samples"],
    )
    reference_rows, _ = evaluate_sequence(
        sequence,
        plan,
        config,
        quadrature["convergence_reference_radial_order"],
        quadrature["convergence_reference_angular_samples"],
    )
    volume_keys = [
        "planned_removal_volume_mm3",
        "actual_removed_volume_mm3",
        "achieved_within_plan_volume_mm3",
        "remaining_within_plan_volume_mm3",
        "overcut_within_plan_volume_mm3",
    ]
    convergence = {
        key: abs(rows[-1][key] - reference_rows[-1][key])
        for key in volume_keys
    }
    checks.update(
        {
            "planned_identity_each_step": all(
                abs(
                    row["planned_removal_volume_mm3"]
                    - row["achieved_within_plan_volume_mm3"]
                    - row["remaining_within_plan_volume_mm3"]
                )
                <= 1e-9
                for row in rows
            ),
            "actual_identity_each_step": all(
                abs(
                    row["actual_removed_volume_mm3"]
                    - row["achieved_within_plan_volume_mm3"]
                    - row["overcut_within_plan_volume_mm3"]
                )
                <= 1e-9
                for row in rows
            ),
            "actual_removal_monotone": bool(
                np.all(
                    np.diff(
                        [row["actual_removed_volume_mm3"] for row in rows]
                    )
                    >= -1e-10
                )
            ),
            "remaining_monotone": bool(
                np.all(
                    np.diff(
                        [
                            row["remaining_within_plan_volume_mm3"]
                            for row in rows
                        ]
                    )
                    <= 1e-10
                )
            ),
            "completion_bounded": all(
                0.0 <= row["completion_fraction"] <= 1.0 for row in rows
            ),
            "quadrature_convergence_within_0p1_mm3": (
                max(convergence.values()) <= 0.1
            ),
        }
    )

    xy, weights, target_z, initial_z, current_z = arrays
    algorithm_bound_mm = float(np.max(sequence["bounds"]))
    uncertainty = []
    nominal_final = rows[-1]
    for scenario in config["scenarios"]:
        interval = uncertain_state(
            initial_z,
            current_z,
            target_z,
            xy,
            weights,
            scenario,
            algorithm_bound_mm,
        )
        interval["id"] = scenario["id"]
        interval["description"] = scenario["description"]
        uncertainty.append(interval)
    interval_keys = {
        "planned_removal_volume_mm3": "planned_removal_volume_interval_mm3",
        "actual_removed_volume_mm3": "actual_removed_volume_interval_mm3",
        "achieved_within_plan_volume_mm3": (
            "achieved_within_plan_volume_interval_mm3"
        ),
        "remaining_within_plan_volume_mm3": (
            "remaining_within_plan_volume_interval_mm3"
        ),
        "overcut_within_plan_volume_mm3": (
            "overcut_within_plan_volume_interval_mm3"
        ),
        "completion_fraction": "completion_fraction_interval",
    }
    checks["uncertainty_intervals_contain_nominal"] = all(
        interval[interval_key][0] - 1e-12
        <= nominal_final[nominal_key]
        <= interval[interval_key][1] + 1e-12
        for interval in uncertainty
        for nominal_key, interval_key in interval_keys.items()
    )
    checks["stress_intervals_not_narrower"] = all(
        (
            uncertainty[-1][interval_key][1]
            - uncertainty[-1][interval_key][0]
        )
        + 1e-12
        >= (
            uncertainty[1][interval_key][1]
            - uncertainty[1][interval_key][0]
        )
        for interval_key in interval_keys.values()
    )
    fields = face_state_fields(
        sequence,
        plan,
        config["scenarios"],
        algorithm_bound_mm,
        config["analysis_region"]["radius_mm"],
    )

    now = datetime.now().astimezone()
    output_root = (
        Path(output_root)
        if output_root is not None
        else HERE / "实验结果" / (now.strftime("%Y%m%d_%H%M%S") + "_real_ct_state")
    )
    output_root.mkdir(parents=True, exist_ok=False)
    np.savez_compressed(output_root / "face_state_fields.npz", **fields)
    result = {
        "schema_version": 1,
        "time_local": now.isoformat(),
        "status": "completed" if all(checks.values()) else "completed_with_failures",
        "scope": (
            "公开真实CT肩胛骨在既有计划坐标系中的"
            f"{config['analysis_region']['radius_mm']:g} mm半径局部图域；"
            "16段轨迹为仿真运动，状态为运动推算值，不是实测磨后骨量"
        ),
        "inputs": {
            "ct_mesh": str(DEMO / "scapula_hill_sachs_001_R.stl"),
            "ct_mesh_sha256": file_hash(DEMO / "scapula_hill_sachs_001_R.stl"),
            "joint": str(JOINT),
            "joint_sha256": file_hash(JOINT),
            "sequence": str(SEQUENCE),
            "sequence_sha256": file_hash(SEQUENCE),
            "sequence_record": str(SEQUENCE_RECORD),
            "sequence_record_sha256": file_hash(SEQUENCE_RECORD),
            "uncertainty_scenarios": str(SCENARIOS),
            "uncertainty_scenarios_sha256": file_hash(SCENARIOS),
            "plan_definition": str(DEMO / "real_bone_demo.py"),
            "plan_definition_sha256": file_hash(DEMO / "real_bone_demo.py"),
            "implementation": str(Path(__file__).resolve()),
            "implementation_sha256": file_hash(Path(__file__).resolve()),
            "test": str(HERE / "test_real_ct_state.py"),
            "test_sha256": file_hash(HERE / "test_real_ct_state.py"),
        },
        "plan": {
            "coordinate_frame": "glenoid plan frame stored in joint.npz transform",
            "analysis_radius_mm": config["analysis_region"]["radius_mm"],
            "full_plan_radius_mm": plan.R_PLATE,
            "post_radius_mm": plan.R_POST,
            "boss_radius_mm": plan.R_BOSS,
            "post_target_z_mm": plan.D_POST,
            "boss_target_z_mm": plan.D_BOSS,
            "outer_target_z_mm": 0.0,
            "full_plan_boundary_included": False,
        },
        "quadrature": {
            **quadrature,
            "sample_count": len(xy),
            "area_weight_sum_mm2": float(np.sum(weights)),
            "expected_analysis_area_mm2": float(
                np.pi * config["analysis_region"]["radius_mm"] ** 2
            ),
            "final_volume_absolute_difference_vs_reference_mm3": convergence,
            "note": (
                "在计划深度跳变半径处分段做极坐标Gauss-Legendre积分；"
                "收敛差只评价数值积分，不包含CT或跟踪误差"
            ),
        },
        "algorithm_surface_bound_mm": algorithm_bound_mm,
        "nominal_states": rows,
        "final_uncertainty_scenarios": uncertainty,
        "face_state_fields": "face_state_fields.npz",
        "status_code_legend": {
            "0": "分析域外或无计划去除",
            "1": "在给定误差上界下确定仍有剩余",
            "2": "在给定误差上界下确定已经过深",
            "3": "误差区间跨越目标，无法确定",
        },
        "checks": checks,
        "interpretation": (
            "区间来自显式上界相加，不是概率置信区间；合成参数不代表"
            "设备规格或临床安全阈值。局部分析域不含完整12.5 mm"
            "计划边界，因此本轮不评价计划外去除"
        ),
    }
    (output_root / "results.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(output_root)
    return result


if __name__ == "__main__":
    run()
