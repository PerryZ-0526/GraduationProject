"""运行G1固定实验矩阵并保存双精度候选与完整验收记录。"""
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from time import perf_counter
from zoneinfo import ZoneInfo
import hashlib
import json
import math
import sys

import numpy as np

from clipped_patch import Rejected, audit_candidate, cumulative_center, generate


HERE = Path(__file__).resolve().parent
CUDA_INPUTS = HERE.parent / "CUDA真实骨面对照"
sys.path.insert(0, str(CUDA_INPUTS))
from coverage_inputs import original_plan


def _source_hashes():
    return {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(HERE.glob("*.py"))
    }


def _json_profile(profile):
    value = asdict(profile)
    value["features"] = list(profile.features)
    return value


def _save_candidate(path, candidate):
    names = sorted(candidate.feature_rings)
    rings = [np.asarray(candidate.feature_rings[name], dtype=np.int64) for name in names]
    offsets = np.cumsum([0, *map(len, rings)], dtype=np.int64)
    np.savez(
        path,
        vertices=np.asarray(candidate.mesh.vertices, dtype=np.float64),
        faces=np.asarray(candidate.mesh.faces, dtype=np.int64),
        face_sources=np.asarray(candidate.face_sources, dtype=np.str_),
        feature_names=np.asarray(names, dtype=np.str_),
        feature_ring_vertices=np.concatenate(rings) if rings else np.empty(0, dtype=np.int64),
        feature_ring_offsets=offsets,
    )


def _case_matrix(plan):
    vertical = [
        item
        for item in plan
        if item["start"][:2] == item["end"][:2]
        and item["start"][2] != item["end"][2]
    ]
    if len(vertical) != 4:
        raise RuntimeError(f"原计划竖直段应为4段，实际为{len(vertical)}段")
    plan_radius = vertical[0]["radius"]
    plan_clip = vertical[0]["clip_radius"]
    activation = math.sqrt(plan_radius**2 - plan_clip**2)
    cases = []
    centers = []
    for spacing in (0.4, 0.25):
        centers.clear()
        for item in vertical:
            centers.extend([item["start"][2], item["end"][2]])
            cases.append(
                {
                    "name": f"plan_step_{item['step']}_h{spacing}",
                    "group": "original_plan_vertical_parameters",
                    "plan_step": item["step"],
                    "center_z": cumulative_center(centers),
                    "tool_radius": item["radius"],
                    "clip_radius": item["clip_radius"],
                    "outer_radius": 4.0,
                    "spacing": spacing,
                    "expected": "accept",
                }
            )
    cases.extend(
        [
            {
                "name": "clip_inactive_shallow",
                "group": "mechanism_control",
                "center_z": 1.8,
                "tool_radius": plan_radius,
                "clip_radius": plan_clip,
                "outer_radius": 4.0,
                "spacing": 0.25,
                "expected": "accept",
            },
            {
                "name": "unclipped_smooth_sweep_seam",
                "group": "mechanism_control",
                "center_z": -1.0,
                "tool_radius": 2.0,
                "clip_radius": 3.0,
                "outer_radius": 4.0,
                "spacing": 0.25,
                "expected": "accept",
            },
            {
                "name": "clip_activation_tangent",
                "group": "degenerate_boundary",
                "center_z": activation,
                "tool_radius": plan_radius,
                "clip_radius": plan_clip,
                "outer_radius": 4.0,
                "spacing": 0.25,
                "expected": "accept",
            },
            {
                "name": "clip_near_tangent_thin_wall",
                "group": "degenerate_boundary",
                "center_z": activation - 1e-4,
                "tool_radius": plan_radius,
                "clip_radius": plan_clip,
                "outer_radius": 4.0,
                "spacing": 0.25,
                "expected": "reject_quality",
            },
            {
                "name": "no_contact",
                "group": "degenerate_boundary",
                "center_z": plan_radius,
                "tool_radius": plan_radius,
                "clip_radius": plan_clip,
                "outer_radius": 4.0,
                "spacing": 0.25,
                "expected": "reject_precondition",
            },
        ]
    )
    return cases


def main():
    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    output = HERE / "实验结果" / now.strftime("%Y%m%d_%H%M%S")
    output.mkdir(parents=True)
    rows = []
    plan = original_plan()
    plan_text = json.dumps(plan, sort_keys=True, separators=(",", ":"))
    data = {
        "schema_version": 1,
        "time_beijing": now.strftime("%Y-%m-%d %H:%M:%S"),
        "status": "running",
        "scope": "解析半空间上的同轴竖直球扫掠与计划圆柱裁剪；非真实骨面整骨重建",
        "units": {"length": "mm", "angle": "degree"},
        "thresholds": {
            "min_angle_deg": 25.0,
            "min_q": 0.4,
            "bidirectional_error_upper_mm": 0.1,
            "certificate_spacing_mm": 0.04,
        },
        "plan_sha256": hashlib.sha256(plan_text.encode()).hexdigest(),
        "plan_source_sha256": hashlib.sha256(
            (CUDA_INPUTS / "coverage_inputs.py").read_bytes()
        ).hexdigest(),
        "cases": rows,
        "source_sha256": _source_hashes(),
    }

    def save():
        (output / "results.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    save()
    try:
        for spec in _case_matrix(plan):
            row = dict(spec)
            rows.append(row)
            started = perf_counter()
            try:
                candidate = generate(
                    center_z=spec["center_z"],
                    tool_radius=spec["tool_radius"],
                    clip_radius=spec["clip_radius"],
                    outer_radius=spec["outer_radius"],
                    spacing=spec["spacing"],
                )
                audit = audit_candidate(candidate)
                mesh_name = f"{spec['name']}.npz"
                _save_candidate(output / mesh_name, candidate)
                row.update(
                    generated=True,
                    profile=_json_profile(candidate.profile),
                    feature_names=sorted(candidate.feature_rings),
                    mesh=mesh_name,
                    audit=audit,
                    accepted=bool(audit["accepted"]),
                )
            except Rejected as exc:
                row.update(
                    generated=False,
                    accepted=False,
                    precondition_rejection=str(exc),
                )
            row["elapsed_ms"] = (perf_counter() - started) * 1000
            expected = row["expected"]
            row["expectation_met"] = bool(
                (expected == "accept" and row["accepted"])
                or (
                    expected == "reject_quality"
                    and not row["accepted"]
                    and "shape_quality" in row.get("audit", {}).get("reasons", [])
                )
                or (
                    expected == "reject_precondition"
                    and not row["generated"]
                )
            )
            save()
            print(
                spec["name"],
                "accepted",
                row["accepted"],
                "expected",
                expected,
                "met",
                row["expectation_met"],
                flush=True,
            )
        data["status"] = (
            "completed"
            if all(row["expectation_met"] for row in rows)
            else "completed_with_unexpected_results"
        )
        plan_cases = [
            row for row in rows
            if row["group"] == "original_plan_vertical_parameters"
        ]
        data["summary"] = {
            "cases": len(rows),
            "expectations_met": sum(row["expectation_met"] for row in rows),
            "plan_parameter_cases_accepted": sum(row["accepted"] for row in plan_cases),
            "plan_parameter_cases_total": len(plan_cases),
            "worst_plan_parameter_min_angle_deg": min(
                row["audit"]["min_angle_deg"] for row in plan_cases
            ),
            "worst_plan_parameter_min_q": min(
                row["audit"]["min_q"] for row in plan_cases
            ),
            "worst_plan_parameter_bidirectional_upper_mm": max(
                max(
                    row["audit"]["mesh_to_target_upper_mm"],
                    row["audit"]["target_to_mesh_upper_mm"],
                )
                for row in plan_cases
            ),
        }
    finally:
        save()
    print(output)


if __name__ == "__main__":
    main()
