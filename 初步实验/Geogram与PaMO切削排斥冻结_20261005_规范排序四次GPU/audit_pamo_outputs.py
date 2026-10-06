"""按输入清单逐例隔离审计PaMO输出，并保留失败状态。"""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from time import perf_counter

import numpy as np
import pyvista as pv
import trimesh

from surface_methods import (
    _distance_summary,
    _distances_to_mesh,
    _face_centers,
    mesh_quality,
    mesh_topology,
)


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def as_polydata(mesh):
    faces = np.asarray(mesh.faces, dtype=np.int64)
    return pv.PolyData(
        np.asarray(mesh.vertices, dtype=np.float64),
        np.column_stack((np.full(len(faces), 3, dtype=np.int64), faces)),
    )


def sampled_mesh_drift(candidate, reference):
    candidate_samples = np.vstack((np.asarray(candidate.points), _face_centers(candidate)))
    reference_samples = np.vstack((np.asarray(reference.points), _face_centers(reference)))
    return {
        "pamo_to_geogram": _distance_summary(_distances_to_mesh(candidate_samples, reference)),
        "geogram_to_pamo": _distance_summary(_distances_to_mesh(reference_samples, candidate)),
        "interpretation": "顶点和面心双向抽样距离，不是连续Hausdorff严格上界",
    }


def area_samples(mesh, count, seed):
    faces = np.asarray(mesh.faces).reshape(-1, 4)[:, 1:]
    triangles = np.asarray(mesh.points, dtype=np.float64)[faces]
    cross = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    weights = np.linalg.norm(cross, axis=1)
    if not np.all(np.isfinite(weights)) or weights.sum() <= 0:
        raise ValueError("参照或候选网格面积无效")
    rng = np.random.default_rng(seed)
    chosen = triangles[rng.choice(len(triangles), count, p=weights / weights.sum())]
    uv = rng.random((count, 2))
    root = np.sqrt(uv[:, 0])
    return ((1 - root[:, None]) * chosen[:, 0]
            + (root * (1 - uv[:, 1]))[:, None] * chosen[:, 1]
            + (root * uv[:, 1])[:, None] * chosen[:, 2])


def reference_audit(candidate, reference):
    candidate_points = area_samples(candidate, 8192, 20260922)
    reference_points = area_samples(reference, 8192, 20260923)
    forward = _distance_summary(_distances_to_mesh(candidate_points, reference))
    backward = _distance_summary(_distances_to_mesh(reference_points, candidate))
    return {
        "pamo_to_reference": forward,
        "reference_to_pamo": backward,
        "sampled_max_mm": max(forward["max_mm"], backward["max_mm"]),
        "interpretation": "每方向8192个固定种子面积样本；参照是0.025 mm规则网格等值面，非连续Hausdorff证书",
    }


def audit_one(source, target, reference_path):
    started = perf_counter()
    geogram = trimesh.load(source, force="mesh", process=False)
    pamo = trimesh.load(target, force="mesh", process=False)
    before = as_polydata(geogram)
    after = as_polydata(pamo)
    input_topology = mesh_topology(before)
    topology = mesh_topology(after)
    quality = mesh_quality(after)
    drift = sampled_mesh_drift(after, before)
    reference = pv.read(reference_path)
    geometry = reference_audit(after, reference)
    quality_passed = quality["bad_faces"] == 0
    topology_passed = (
        topology["connected_components"] == 1
        and topology["boundary_edges"] == 0
        and topology["non_manifold_edges"] == 0
        and topology["inconsistent_interior_edges"] == 0
        and topology["self_intersection_faces"] == 0
        and bool(pamo.is_watertight)
        and bool(pamo.is_winding_consistent)
    )
    return {
        "input_quality": mesh_quality(before),
        "input_topology": input_topology,
        "input_validity_status": (
            "detector_flags_pending_review"
            if input_topology["self_intersection_faces"] > 0
            else "passes_listed_topology_checks"
        ),
        "output_quality": quality,
        "output_topology": topology,
        "output_watertight": bool(pamo.is_watertight),
        "output_winding_consistent": bool(pamo.is_winding_consistent),
        "sampled_drift": drift,
        "sampled_reference_geometry": geometry,
        "quality_passed": quality_passed,
        "topology_passed": topology_passed,
        "sampled_geometry_passed": geometry["sampled_max_mm"] <= 0.1,
        "accepted_under_sampled_protocol": quality_passed and topology_passed and geometry["sampled_max_mm"] <= 0.1,
        "continuous_error_certificate_status": "not_available",
        "accepted_under_common_budget": None,
        "audit_wall_ms": (perf_counter() - started) * 1000.0,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("prepared_manifest", type=Path)
    parser.add_argument("pamo_outputs", type=Path)
    parser.add_argument("--case", nargs=4, metavar=("INPUT", "OUTPUT", "REFERENCE", "RESULT"))
    args = parser.parse_args()
    if args.case:
        source, target, reference, result = map(Path, args.case)
        result.write_text(json.dumps(audit_one(source, target, reference), ensure_ascii=False, indent=2), encoding="utf-8")
        return 0

    manifest_path = args.prepared_manifest.resolve()
    outputs = args.pamo_outputs.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    remote_path = outputs / "remote_results.json"
    remote = json.loads(remote_path.read_text(encoding="utf-8"))
    remote_rows = {row["case_id"]: row for row in remote["runs"]}
    now = datetime.now(timezone(timedelta(hours=8)))
    report = {
        "schema_version": 2,
        "time_beijing": now.strftime("%Y-%m-%d %H:%M:%S"),
        "status": "running",
        "prepared_manifest_sha256": file_hash(manifest_path),
        "remote_results_sha256": file_hash(remote_path),
        "cases": [],
    }
    report_path = outputs / "audit.json"

    def save():
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    save()
    for item in manifest["inputs"]:
        case_id = item["case_id"]
        row = {"case_id": case_id, "status": "audit_failed", "reasons": []}
        report["cases"].append(row)
        remote_row = remote_rows.get(case_id)
        if remote_row is None:
            row["status"] = "execution_missing"
            row["reasons"].append("远端无该案例执行记录")
        elif remote_row.get("exit_code") != 0 or not remote_row.get("output"):
            row["status"] = "execution_failed"
            row["reasons"].append(f"远端执行退出码: {remote_row.get('exit_code')}")
        else:
            source = Path(item["source"])
            target = outputs / remote_row["output"]
            if not source.is_file() or file_hash(source) != item["sha256"]:
                row["status"] = "input_invalid"
                row["reasons"].append("本地Geogram输入缺失或摘要不匹配")
            elif not target.is_file() or file_hash(target) != remote_row.get("output_sha256"):
                row["status"] = "output_invalid"
                row["reasons"].append("PaMO输出缺失或摘要不匹配")
            elif remote_row.get("input_sha256") != item["sha256"]:
                row["status"] = "input_invalid"
                row["reasons"].append("远端实际输入摘要不匹配")
            elif not item.get("reference") or not Path(item["reference"]).is_file():
                row["status"] = "reference_invalid"
                row["reasons"].append("独立三维参照缺失")
            elif file_hash(item["reference"]) != item.get("reference_sha256"):
                row["status"] = "reference_invalid"
                row["reasons"].append("独立三维参照摘要不匹配")
            else:
                result_path = outputs / f"{case_id}_audit_detail.json"
                try:
                    completed = subprocess.run(
                        [sys.executable, "-B", "-X", "utf8", str(Path(__file__).resolve()),
                         str(manifest_path), str(outputs), "--case", str(source), str(target),
                         str(item["reference"]), str(result_path)],
                        capture_output=True, text=True, timeout=600, check=False,
                    )
                    exit_code = completed.returncode
                    detail = completed.stdout + completed.stderr
                except subprocess.TimeoutExpired as error:
                    exit_code = 124
                    detail = "审计子进程超时: " + str(error)
                if exit_code == 0 and result_path.is_file():
                    row.update(json.loads(result_path.read_text(encoding="utf-8")))
                    row["status"] = "audited"
                else:
                    row["reasons"].append(f"审计子进程退出码: {exit_code}")
                    (outputs / f"{case_id}_audit.log").write_text(
                        detail, encoding="utf-8"
                    )
        save()
        print(case_id, row["status"], flush=True)

    report["status"] = "completed" if all(row["status"] == "audited" for row in report["cases"]) else "completed_with_failures"
    save()
    print(report_path)
    return 0 if report["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
