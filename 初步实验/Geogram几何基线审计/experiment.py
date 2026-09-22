"""独立审计Geogram在连续球形磨削任务中的几何基线能力。"""
from datetime import datetime
from hashlib import sha256
import json
import platform
from pathlib import Path
import subprocess
import sys
from time import perf_counter
from zoneinfo import ZoneInfo

import numpy as np
import pyvista as pv
import trimesh


HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[1]
COMMON = HERE.parent / "共同运动记录与方法对照"
STITCH = HERE.parent / "真实骨面共边拼接"
sys.path.insert(0, str(COMMON))
sys.path.insert(0, str(STITCH))

from geogram_baseline import (  # noqa: E402
    DEFAULT_BINARY,
    GEOGRAM_COMMIT,
    _capsule_mesh,
    _export_double_obj,
    _slab_mesh,
    _top_surface,
    effective_primitives,
    geogram_surface,
)
from motion_record import load_document, replay_case  # noqa: E402
from pymeshlab_isolation import self_intersection_flags  # noqa: E402
from surface_methods import (  # noqa: E402
    _distance_summary,
    _distances_to_mesh,
    _face_centers,
    height_surface,
    mesh_quality,
    sampled_surface_audit,
)


XY_BOUNDS = (-2.0, 2.0, -2.0, 2.0)
Z_BOUNDS = (-0.9, 0.9)
SLAB_SPACING_MM = 0.1
DENSE_TARGET_SPACING_MM = 0.025
GEOMETRY_BUDGET_MM = 0.1
TIMEOUT_S = 60


def _hash_file(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def _faces(polydata):
    return np.asarray(polydata.faces, dtype=np.int64).reshape(-1, 4)[:, 1:]


def _surface_topology(surface):
    faces = _faces(surface)
    directed = np.concatenate(
        (faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]),
        axis=0,
    )
    edges, inverse, counts = np.unique(
        np.sort(directed, axis=1),
        axis=0,
        return_inverse=True,
        return_counts=True,
    )
    direction = np.where(directed[:, 0] < directed[:, 1], 1, -1)
    direction_sum = np.bincount(inverse, weights=direction)
    inconsistent = (counts == 2) & (direction_sum != 0)
    regions = np.asarray(surface.connectivity().cell_data["RegionId"])
    flags = self_intersection_flags(
        np.asarray(surface.points, dtype=np.float64),
        faces,
    )
    return {
        "connected_components": int(np.max(regions, initial=-1) + 1),
        "unique_edges": int(len(edges)),
        "boundary_edges": int(np.count_nonzero(counts == 1)),
        "non_manifold_edges": int(np.count_nonzero(counts > 2)),
        "inconsistent_interior_edges": int(np.count_nonzero(inconsistent)),
        "self_intersection_flag_faces": int(np.count_nonzero(flags)),
        "self_intersection_interpretation": (
            "PyMeshLab检测器报警面数量，未经精确复核时不等同于真实穿插面"
        ),
    }


def _full_solid_metrics(path):
    mesh = trimesh.load(path, force="mesh", process=False)
    return {
        "vertices": int(len(mesh.vertices)),
        "faces": int(len(mesh.faces)),
        "watertight": bool(mesh.is_watertight),
        "winding_consistent": bool(mesh.is_winding_consistent),
        "euler_number": int(mesh.euler_number),
        "body_count": int(mesh.body_count),
        "volume_mm3": float(mesh.volume),
    }


def _audit_surface(surface, diagnostics, dense_target, case, replay):
    quality = mesh_quality(surface)
    quality["bad_face_fraction"] = (
        quality["bad_faces"] / quality["faces"] if quality["faces"] else 0.0
    )
    topology = _surface_topology(surface)
    geometry = sampled_surface_audit(surface, dense_target, case, replay)
    sampled_max = max(
        geometry[name]["max_mm"]
        for name in (
            "implicit_residual",
            "mesh_to_dense_target",
            "dense_target_to_mesh",
        )
    )
    full_solid = _full_solid_metrics(diagnostics["final_full_mesh"])
    geometry_gate = sampled_max <= GEOMETRY_BUDGET_MM
    solid_gate = (
        full_solid["watertight"]
        and full_solid["winding_consistent"]
        and full_solid["body_count"] == 1
        and full_solid["euler_number"] == 2
    )
    quality_gate = (
        quality["bad_faces"] == 0
        and topology["non_manifold_edges"] == 0
        and topology["inconsistent_interior_edges"] == 0
        and topology["self_intersection_flag_faces"] == 0
    )
    return {
        "diagnostics": diagnostics,
        "full_solid": full_solid,
        "top_surface_quality": quality,
        "top_surface_topology": topology,
        "sampled_geometry": geometry,
        "sampled_geometry_max_mm": sampled_max,
        "geometry_gate": geometry_gate,
        "full_solid_gate": solid_gate,
        "quality_gate": quality_gate,
        "accepted_as_geometry_baseline": geometry_gate and solid_gate,
        "accepted_as_complete_mesh_delivery": (
            geometry_gate and solid_gate and quality_gate
        ),
    }


def _surface_distance(first, second):
    first_samples = np.vstack(
        (np.asarray(first.points, dtype=np.float64), _face_centers(first))
    )
    second_samples = np.vstack(
        (np.asarray(second.points, dtype=np.float64), _face_centers(second))
    )
    first_to_second = _distance_summary(
        _distances_to_mesh(first_samples, second)
    )
    second_to_first = _distance_summary(
        _distances_to_mesh(second_samples, first)
    )
    return {
        "first_to_second": first_to_second,
        "second_to_first": second_to_first,
        "bidirectional_sampled_max_mm": max(
            first_to_second["max_mm"],
            second_to_first["max_mm"],
        ),
        "interpretation": "顶点和面心的双向抽样距离，不是连续Hausdorff距离",
    }


def _tool_discretization(replay, subdivisions):
    primitives, _ = effective_primitives(replay["primitives"])
    primitive = primitives[0]
    radius = float(primitive["radius"])
    sphere = trimesh.creation.icosphere(subdivisions=subdivisions, radius=1.0)
    plane_distances = np.einsum(
        "ij,ij->i",
        np.asarray(sphere.face_normals),
        np.asarray(sphere.triangles)[:, 0],
    )
    capsule = _capsule_mesh(primitive, subdivisions=subdivisions)
    length = float(
        np.linalg.norm(
            np.asarray(primitive["end"]) - np.asarray(primitive["start"])
        )
    )
    analytic_volume = (
        np.pi * radius * radius * length
        + 4.0 * np.pi * radius**3 / 3.0
    )
    return {
        "subdivisions": subdivisions,
        "sphere_faces": int(len(sphere.faces)),
        "capsule_faces": int(len(capsule.faces)),
        "radial_deficit_bound_mm": float(
            radius * (1.0 - np.min(plane_distances))
        ),
        "analytic_capsule_volume_mm3": float(analytic_volume),
        "mesh_capsule_volume_mm3": float(capsule.volume),
        "volume_deficit_mm3": float(analytic_volume - capsule.volume),
        "relative_volume_deficit": float(
            (analytic_volume - capsule.volume) / analytic_volume
        ),
    }


def _run_boolean(
    left,
    right,
    output,
    operation,
    log_path,
    no_simplify=False,
):
    command = [
        str(DEFAULT_BINARY),
        "--operation",
        operation,
    ]
    if no_simplify:
        command.append("--no-simplify")
    command.extend((str(left), str(right), str(output)))
    started = perf_counter()
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=TIMEOUT_S,
        check=False,
    )
    elapsed_ms = (perf_counter() - started) * 1000.0
    Path(log_path).write_text(
        completed.stdout + completed.stderr,
        encoding="utf-8",
    )
    if completed.returncode or not Path(output).is_file():
        raise RuntimeError(
            f"Geogram {operation}失败，返回码{completed.returncode}"
        )
    return {
        "operation": operation,
        "command": command,
        "elapsed_ms": elapsed_ms,
        "log": Path(log_path).name,
        "output": Path(output).name,
    }


def _cumulative_union_surface(case, replay, work_directory, subdivisions=3):
    work_directory.mkdir(parents=True, exist_ok=True)
    initial = _slab_mesh(
        case,
        XY_BOUNDS,
        Z_BOUNDS[0],
        SLAB_SPACING_MM,
    )
    initial_path = work_directory / "initial.obj"
    _export_double_obj(initial_path, initial)
    primitives, removed = effective_primitives(replay["primitives"])
    tool_paths = []
    for index, primitive in enumerate(primitives):
        tool_path = work_directory / f"tool_{index}.obj"
        _export_double_obj(
            tool_path,
            _capsule_mesh(primitive, subdivisions=subdivisions),
        )
        tool_paths.append(tool_path)
    if not tool_paths:
        raise ValueError("累计并集参照至少需要一个有效工具原语")

    rows = []
    union_path = tool_paths[0]
    started = perf_counter()
    for index, tool_path in enumerate(tool_paths[1:], start=1):
        output_path = work_directory / f"union_{index}.obj"
        rows.append(
            _run_boolean(
                union_path,
                tool_path,
                output_path,
                "union",
                work_directory / f"union_{index}.log",
            )
        )
        union_path = output_path
    output_path = work_directory / "difference.obj"
    rows.append(
        _run_boolean(
            initial_path,
            union_path,
            output_path,
            "difference",
            work_directory / "difference.log",
        )
    )
    full_mesh = trimesh.load(output_path, force="mesh", process=False)
    surface = _top_surface(full_mesh)
    return surface, {
        "implementation": (
            "Geogram工具原语累计并集后，对初始厚片执行一次mesh_difference"
        ),
        "commit": GEOGRAM_COMMIT,
        "binary": str(DEFAULT_BINARY),
        "binary_sha256": _hash_file(DEFAULT_BINARY),
        "tool_subdivisions": subdivisions,
        "input_primitive_count": len(replay["primitives"]),
        "effective_primitive_count": len(primitives),
        "redundant_contained_event_ids": removed,
        "steps": rows,
        "elapsed_ms": (perf_counter() - started) * 1000.0,
        "final_full_mesh": str(output_path),
        "scope": (
            "工具并集本身仍由两两精确布尔构造；该分支只隔离"
            "骨面逐步回灌与最终一次差集的差异"
        ),
    }


def _segmented_replays(replay):
    primitives, _ = effective_primitives(replay["primitives"])
    primitive = primitives[0]
    middle = (
        np.asarray(primitive["start"], dtype=np.float64)
        + np.asarray(primitive["end"], dtype=np.float64)
    ) / 2.0
    full = {
        **replay,
        "primitives": [
            {
                **primitive,
                "event_id": "full_path",
            }
        ],
    }
    segmented = {
        **replay,
        "primitives": [
            {
                **primitive,
                "event_id": "segment_0",
                "end": middle,
            },
            {
                **primitive,
                "event_id": "segment_1",
                "start": middle,
            },
        ],
    }
    return full, segmented


def _run_variant(
    name,
    case,
    replay,
    dense_target,
    output,
    **kwargs,
):
    work_directory = output / name
    surface, diagnostics = geogram_surface(
        case,
        replay,
        XY_BOUNDS,
        Z_BOUNDS,
        SLAB_SPACING_MM,
        work_directory,
        **kwargs,
    )
    surface_name = f"{name}.vtp"
    surface.save(output / surface_name)
    row = _audit_surface(surface, diagnostics, dense_target, case, replay)
    row["name"] = name
    row["surface"] = surface_name
    return row, surface


def main():
    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    output = HERE / "实验结果" / now.strftime("%Y%m%d_%H%M%S")
    output.mkdir(parents=True)
    result = {
        "schema_version": 1,
        "time_beijing": now.strftime("%Y-%m-%d %H:%M:%S"),
        "status": "running",
        "research_question": (
            "Geogram作为精确CSG基线时，工具离散、共面简化和连续"
            "布尔组织方式分别怎样影响几何、拓扑、网格质量与耗时"
        ),
        "scope": (
            "解析倾斜平面与球形工具仿真；不含真实CT误差、真实运动、"
            "质量维护、CUDA或临床结论"
        ),
        "environment": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "machine": platform.machine(),
        },
        "geogram": {
            "commit": GEOGRAM_COMMIT,
            "binary": str(DEFAULT_BINARY),
            "binary_sha256": _hash_file(DEFAULT_BINARY),
            "source_repository": "https://github.com/BrunoLevy/geogram",
            "paper_doi": "10.1145/3744642",
            "license": "BSD-3-Clause",
        },
        "thresholds": {
            "geometry_budget_mm": GEOMETRY_BUDGET_MM,
            "minimum_angle_deg": 25.0,
            "minimum_q": 0.4,
            "boolean_timeout_s": TIMEOUT_S,
        },
        "source_sha256": {
            str(path.relative_to(PROJECT_ROOT)): _hash_file(path)
            for path in (
                Path(__file__),
                COMMON / "geogram_baseline.py",
                COMMON / "geogram_boolean.cpp",
                COMMON / "build_geogram_baseline.sh",
                COMMON / "cases.json",
            )
        },
        "runs": {},
        "comparisons": {},
    }

    def save():
        (output / "results.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    save()
    try:
        document = load_document()
        case = next(
            item
            for item in document["cases"]
            if item["id"] == "tilted_crossing_paths"
        )
        replay = replay_case(case, document["replay_policy"])
        dense_target, dense_diagnostics = height_surface(
            case,
            replay,
            XY_BOUNDS,
            DENSE_TARGET_SPACING_MM,
        )
        dense_target.save(output / "dense_target.vtp")
        result["input"] = {
            "case_id": case["id"],
            "record_kind": document["record_kind"],
            "xy_bounds_mm": XY_BOUNDS,
            "z_bounds_mm": Z_BOUNDS,
            "slab_spacing_mm": SLAB_SPACING_MM,
            "dense_target_spacing_mm": DENSE_TARGET_SPACING_MM,
            "primitive_count": len(replay["primitives"]),
            "dense_target_diagnostics": dense_diagnostics,
        }

        surfaces = {}
        for subdivisions in (1, 2, 3, 4):
            name = f"resolution_s{subdivisions}"
            result["runs"][name], surfaces[name] = _run_variant(
                name,
                case,
                replay,
                dense_target,
                output,
                tool_subdivisions=subdivisions,
            )
            result["runs"][name]["tool_discretization"] = (
                _tool_discretization(replay, subdivisions)
            )
            save()

        result["runs"]["no_simplify_s3"], surfaces["no_simplify_s3"] = (
            _run_variant(
                "no_simplify_s3",
                case,
                replay,
                dense_target,
                output,
                tool_subdivisions=3,
                no_simplify=True,
            )
        )
        save()

        reversed_replay = {
            **replay,
            "primitives": list(reversed(replay["primitives"])),
        }
        result["runs"]["reversed_order_s3"], surfaces["reversed_order_s3"] = (
            _run_variant(
                "reversed_order_s3",
                case,
                reversed_replay,
                dense_target,
                output,
                tool_subdivisions=3,
            )
        )
        save()

        effective, _ = effective_primitives(replay["primitives"])
        repeated_replay = {
            **replay,
            "primitives": effective + effective,
        }
        result["repeat_stress"] = {
            "requested_trials": 5,
            "same_input_each_trial": True,
            "reason": (
                "探索轮出现相同输入一次内核终止、一次返回非水密结果，"
                "因此固定输入重复运行以检查稳定性"
            ),
            "trials": [],
        }
        for trial_index in range(result["repeat_stress"]["requested_trials"]):
            name = f"repeated_tools_s3_trial_{trial_index}"
            try:
                row, surface = _run_variant(
                    name,
                    case,
                    repeated_replay,
                    dense_target,
                    output,
                    tool_subdivisions=3,
                    deduplicate_contained=False,
                )
                row["status"] = "returned"
                result["repeat_stress"]["trials"].append(row)
                surfaces[name] = surface
            except Exception as error:
                work_directory = output / name
                completed_outputs = sorted(
                    work_directory.glob("difference_*.obj"),
                    key=lambda path: int(path.stem.split("_")[-1]),
                )
                failure_logs = sorted(
                    work_directory.glob("difference_*.log"),
                    key=lambda path: int(path.stem.split("_")[-1]),
                )
                row = {
                    "name": name,
                    "status": "failed",
                    "error": str(error),
                    "successful_difference_steps": len(completed_outputs),
                    "interpretation": (
                        "完全重复工具是集合幂等性压力测试；作者内核面对"
                        "共面或重合束可能终止，因此实际连续管线需要先"
                        "消除被既有工具集合完全包含的冗余原语"
                    ),
                }
                if failure_logs:
                    row["failure_log"] = str(
                        failure_logs[-1].relative_to(output)
                    )
                    row["failure_log_tail"] = (
                        failure_logs[-1]
                        .read_text(encoding="utf-8")
                        .splitlines()[-12:]
                    )
                if completed_outputs:
                    partial_mesh = trimesh.load(
                        completed_outputs[-1],
                        force="mesh",
                        process=False,
                    )
                    partial_surface = _top_surface(partial_mesh)
                    partial_name = f"{name}_partial.vtp"
                    partial_surface.save(output / partial_name)
                    partial_diagnostics = {
                        "implementation": (
                            "Geogram重复原语压力测试在失败前的最后完整输出"
                        ),
                        "commit": GEOGRAM_COMMIT,
                        "binary": str(DEFAULT_BINARY),
                        "binary_sha256": _hash_file(DEFAULT_BINARY),
                        "tool_subdivisions": 3,
                        "elapsed_ms": None,
                        "final_full_mesh": str(completed_outputs[-1]),
                        "scope": (
                            "失败前中间状态，只用于定位集合幂等性问题"
                        ),
                    }
                    row["partial_before_failure"] = _audit_surface(
                        partial_surface,
                        partial_diagnostics,
                        dense_target,
                        case,
                        repeated_replay,
                    )
                    row["partial_before_failure"]["surface"] = partial_name
                    surfaces[f"{name}_partial"] = partial_surface
                result["repeat_stress"]["trials"].append(row)
            save()

        batch_surface, batch_diagnostics = _cumulative_union_surface(
            case,
            replay,
            output / "cumulative_union_s3",
            subdivisions=3,
        )
        batch_surface.save(output / "cumulative_union_s3.vtp")
        result["runs"]["cumulative_union_s3"] = _audit_surface(
            batch_surface,
            batch_diagnostics,
            dense_target,
            case,
            replay,
        )
        result["runs"]["cumulative_union_s3"].update(
            name="cumulative_union_s3",
            surface="cumulative_union_s3.vtp",
        )
        surfaces["cumulative_union_s3"] = batch_surface
        save()

        full_replay, segmented_replay = _segmented_replays(replay)
        full_target, _ = height_surface(
            case,
            full_replay,
            XY_BOUNDS,
            DENSE_TARGET_SPACING_MM,
        )
        for name, variant_replay in (
            ("single_path_s3", full_replay),
            ("segmented_path_s3", segmented_replay),
        ):
            result["runs"][name], surfaces[name] = _run_variant(
                name,
                case,
                variant_replay,
                full_target,
                output,
                tool_subdivisions=3,
                deduplicate_contained=False,
            )
            save()

        baseline = surfaces["resolution_s3"]
        comparison_pairs = {
            "default_vs_no_simplify": (
                baseline,
                surfaces["no_simplify_s3"],
            ),
            "forward_vs_reversed_order": (
                baseline,
                surfaces["reversed_order_s3"],
            ),
            "sequential_vs_cumulative_union": (
                baseline,
                surfaces["cumulative_union_s3"],
            ),
            "single_vs_segmented_path": (
                surfaces["single_path_s3"],
                surfaces["segmented_path_s3"],
            ),
        }
        for name, surface in surfaces.items():
            if name.startswith("repeated_tools_s3_trial_"):
                comparison_pairs[f"baseline_vs_{name}"] = (
                    baseline,
                    surface,
                )
        result["comparisons"] = {
            name: _surface_distance(*pair)
            for name, pair in comparison_pairs.items()
        }
        result["summary"] = {
            "resolution_runs_completed": sum(
                f"resolution_s{subdivisions}" in result["runs"]
                for subdivisions in (1, 2, 3, 4)
            ),
            "geometry_baseline_passed": sum(
                bool(row.get("accepted_as_geometry_baseline"))
                for row in result["runs"].values()
            ),
            "complete_mesh_delivery_passed": sum(
                bool(row.get("accepted_as_complete_mesh_delivery"))
                for row in result["runs"].values()
            ),
            "repeat_stress_completed": (
                len(result["repeat_stress"]["trials"])
                == result["repeat_stress"]["requested_trials"]
            ),
            "repeat_trials_returned": sum(
                row["status"] == "returned"
                for row in result["repeat_stress"]["trials"]
            ),
            "repeat_trials_failed": sum(
                row["status"] == "failed"
                for row in result["repeat_stress"]["trials"]
            ),
            "repeat_trials_geometry_baseline_passed": sum(
                bool(row.get("accepted_as_geometry_baseline"))
                for row in result["repeat_stress"]["trials"]
            ),
            "maximum_invariance_sampled_delta_mm": max(
                row["bidirectional_sampled_max_mm"]
                for row in result["comparisons"].values()
            ),
        }
        result["status"] = "completed"
        save()
    except Exception as error:
        result["status"] = "failed"
        result["error"] = str(error)
        save()
        raise
    print(output)


if __name__ == "__main__":
    main()
