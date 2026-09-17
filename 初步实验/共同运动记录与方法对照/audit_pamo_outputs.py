"""按共同质量、拓扑和几何预算审计PaMO远端输出。"""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pyvista as pv
import trimesh

from geogram_baseline import _top_surface
from motion_record import load_document, replay_case
from surface_methods import (
    _distance_summary,
    _distances_to_mesh,
    _face_centers,
    height_surface,
    mesh_quality,
    mesh_topology,
    sampled_surface_audit,
)


HERE = Path(__file__).resolve().parent
GEOMETRY_BUDGET_MM = 0.1


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def as_polydata(mesh):
    faces = np.asarray(mesh.faces, dtype=np.int64)
    return pv.PolyData(
        np.asarray(mesh.vertices, dtype=np.float64),
        np.column_stack((np.full(len(faces), 3, dtype=np.int64), faces)),
    )


def sampled_mesh_drift(candidate, reference):
    candidate_samples = np.vstack(
        (np.asarray(candidate.points), _face_centers(candidate))
    )
    reference_samples = np.vstack(
        (np.asarray(reference.points), _face_centers(reference))
    )
    return {
        "pamo_to_geogram": _distance_summary(
            _distances_to_mesh(candidate_samples, reference)
        ),
        "geogram_to_pamo": _distance_summary(
            _distances_to_mesh(reference_samples, candidate)
        ),
        "interpretation": "顶点和面心双向抽样距离，不是连续Hausdorff严格上界",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("experiment", type=Path)
    parser.add_argument("pamo_outputs", type=Path)
    args = parser.parse_args()

    experiment = args.experiment.resolve()
    pamo_outputs = args.pamo_outputs.resolve()
    common_result_path = experiment / "results.json"
    remote_result_path = pamo_outputs / "remote_results.json"
    common_result = json.loads(common_result_path.read_text(encoding="utf-8"))
    remote_result = json.loads(remote_result_path.read_text(encoding="utf-8"))
    document = load_document(HERE / "quality_failure_cases_v2.json")
    cases = {case["id"]: case for case in document["cases"]}
    remote_rows = {row["case_id"]: row for row in remote_result["runs"]}

    output = {
        "schema_version": 1,
        "time_local": datetime.now().astimezone().isoformat(),
        "status": "running",
        "method": "PaMO作者三阶段输出的本项目独立外部审计",
        "source_results": str(common_result_path),
        "source_results_sha256": file_hash(common_result_path),
        "remote_results": str(remote_result_path),
        "remote_results_sha256": file_hash(remote_result_path),
        "pamo_commit": remote_result["upstream_commit"],
        "pamo_license": remote_result["license"],
        "parameters": remote_result["parameters"],
        "geometry_budget_mm": GEOMETRY_BUDGET_MM,
        "cases": [],
    }
    output_path = pamo_outputs / "audit.json"

    def save():
        output_path.write_text(
            json.dumps(output, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    save()
    for common_row in common_result["quality_failure_challenge"]["cases"]:
        case_id = common_row["case_id"]
        case = cases[case_id]
        remote_row = remote_rows[case_id]
        step = common_row["methods"]["geogram_exact_csg"]["diagnostics"]["steps"][-1]
        geogram_path = experiment / f"{case_id}_geogram_work" / step["output"]
        pamo_path = pamo_outputs / remote_row["output"]
        if file_hash(geogram_path) != remote_row["input_sha256"]:
            raise RuntimeError(f"{case_id}: 远端输入摘要不匹配")
        if file_hash(pamo_path) != remote_row["output_sha256"]:
            raise RuntimeError(f"{case_id}: 远端输出摘要不匹配")

        geogram_full = trimesh.load(geogram_path, force="mesh", process=False)
        pamo_full = trimesh.load(pamo_path, force="mesh", process=False)
        geogram_full_pv = as_polydata(geogram_full)
        pamo_full_pv = as_polydata(pamo_full)
        geogram_top = _top_surface(geogram_full)
        pamo_top = _top_surface(pamo_full)
        replay = replay_case(case, document["replay_policy"])
        dense_target, _ = height_surface(
            case,
            replay,
            (-2.0, 2.0, -2.0, 2.0),
            0.025,
        )

        before_target = sampled_surface_audit(
            geogram_top,
            dense_target,
            case,
            replay,
        )
        after_target = sampled_surface_audit(
            pamo_top,
            dense_target,
            case,
            replay,
        )
        drift = sampled_mesh_drift(pamo_full_pv, geogram_full_pv)
        before = {
            "full_quality": mesh_quality(geogram_full_pv),
            "full_topology": mesh_topology(geogram_full_pv),
            "top_quality": mesh_quality(geogram_top),
            "top_topology": mesh_topology(geogram_top),
            "target_audit": before_target,
        }
        after = {
            "full_quality": mesh_quality(pamo_full_pv),
            "full_topology": mesh_topology(pamo_full_pv),
            "top_quality": mesh_quality(pamo_top),
            "top_topology": mesh_topology(pamo_top),
            "target_audit": after_target,
        }
        target_max = max(
            section["max_mm"] for section in after_target.values()
            if isinstance(section, dict)
        )
        drift_max = max(section["max_mm"] for section in drift.values()
                        if isinstance(section, dict))
        accepted = (
            after["top_quality"]["bad_faces"] == 0
            and after["full_topology"]["connected_components"] == 1
            and after["full_topology"]["boundary_edges"] == 0
            and after["full_topology"]["non_manifold_edges"] == 0
            and after["full_topology"]["inconsistent_interior_edges"] == 0
            and after["full_topology"]["self_intersection_faces"] == 0
            and bool(pamo_full.is_watertight)
            and bool(pamo_full.is_winding_consistent)
            and target_max <= GEOMETRY_BUDGET_MM
            and drift_max <= GEOMETRY_BUDGET_MM
        )
        output["cases"].append(
            {
                "case_id": case_id,
                "geogram_input": str(geogram_path),
                "pamo_output": str(pamo_path),
                "remote_run": remote_row,
                "before": before,
                "after": after,
                "pamo_full_watertight": bool(pamo_full.is_watertight),
                "pamo_full_winding_consistent": bool(
                    pamo_full.is_winding_consistent
                ),
                "pamo_full_euler_number": int(pamo_full.euler_number),
                "sampled_drift": drift,
                "sampled_target_max_mm": target_max,
                "sampled_drift_max_mm": drift_max,
                "accepted_under_common_budget": accepted,
            }
        )
        save()
        print(case_id, accepted, flush=True)

    output["accepted_cases"] = sum(
        row["accepted_under_common_budget"] for row in output["cases"]
    )
    output["total_cases"] = len(output["cases"])
    output["status"] = "completed"
    save()
    print(output_path)


if __name__ == "__main__":
    raise SystemExit(main())
