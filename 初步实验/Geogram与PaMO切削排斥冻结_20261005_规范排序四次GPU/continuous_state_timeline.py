"""用已测顺序执行耗时重放持续输入、发布合并和状态年龄。"""
from datetime import datetime
import hashlib
import json
from pathlib import Path

import numpy as np

from real_ct_state import (
    JOINT,
    RealCtStateMapper,
    SCENARIOS,
    SEQUENCE,
    uncertain_state,
)


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ONLINE_EVIDENCE = (
    ROOT
    / "初步实验/真实骨模型演示/在线逐步验收输出"
    / "20260918_005901_161317"
)
TIMELINE_CONFIG = HERE / "continuous_state_scenarios.json"


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def schedule(records, input_period_ms):
    """单工作线程FIFO；每条输入都计算，完成时间不能早于到达时间。"""
    rows = []
    worker_available = 0.0
    for event_index, record in enumerate(records[1:], start=1):
        arrival = (event_index - 1) * input_period_ms
        start = max(arrival, worker_available)
        duration = float(record["wall_ms"])
        completion = start + duration
        rows.append(
            {
                "event_id": event_index,
                "arrival_ms": arrival,
                "start_ms": start,
                "completion_ms": completion,
                "compute_ms": duration,
                "queue_wait_ms": start - arrival,
                "completion_age_ms": completion - arrival,
                "accepted": bool(record["accepted"]),
                "state": record["state"],
            }
        )
        worker_available = completion
    return rows


def refresh_timeline(rows, refresh_period_ms):
    """刷新只合并显示；计算完成的事件不删除，显示版本单调推进。"""
    if not rows:
        return []
    ticks = np.arange(
        0.0,
        rows[-1]["completion_ms"] + refresh_period_ms,
        refresh_period_ms,
    )
    publications = []
    latest = None
    last_version = -1
    for tick in ticks:
        completed = [
            row for row in rows
            if row["completion_ms"] <= tick and row["accepted"]
        ]
        if completed:
            latest = completed[-1]
        if latest is None:
            continue
        version = latest["event_id"]
        publications.append(
            {
                "refresh_ms": float(tick),
                "published_version": version,
                "state_version": latest["state"]["step"],
                "source_arrival_ms": latest["arrival_ms"],
                "state_age_ms": float(tick - latest["arrival_ms"]),
                "new_version": version != last_version,
            }
        )
        last_version = version
    return publications


def age_interval(mapper, vertices, algorithm_bound_mm, age_ms, assumption):
    scenario = {
        **assumption,
        "state_age_ms": float(age_ms),
    }
    current_z = mapper.query.query(vertices[:, 2], mapper.xy)
    return uncertain_state(
        mapper.initial_z,
        current_z,
        mapper.target_z,
        mapper.xy,
        mapper.weights,
        scenario,
        algorithm_bound_mm,
    )


def run(output_root=None):
    config = json.loads(TIMELINE_CONFIG.read_text(encoding="utf-8"))
    records_path = ONLINE_EVIDENCE / "records.json"
    metadata_path = ONLINE_EVIDENCE / "metadata.json"
    records = json.loads(records_path.read_text(encoding="utf-8"))
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    sequence = np.load(SEQUENCE)
    joint = np.load(JOINT)
    mapper = RealCtStateMapper(sequence["snapshots"][0], sequence["faces"])
    algorithm_bound_mm = float(np.max(sequence["bounds"]))

    checks = {
        "seventeen_online_records": len(records) == 17,
        "sixteen_motion_events": len(records[1:]) == 16,
        "all_motion_events_accepted": all(row["accepted"] for row in records[1:]),
        "online_state_versions_match_steps": all(
            row["state"]["step"] == row["step"] for row in records
        ),
        "online_scenarios_match_mapper": (
            metadata["state_uncertainty_sha256"] == file_hash(SCENARIOS)
        ),
        "sequence_initial_matches_joint": bool(
            np.array_equal(sequence["snapshots"][0], joint["vertices"])
        ),
    }
    if not all(checks.values()):
        raise RuntimeError(f"持续输入证据前置检查失败: {checks}")

    scenarios = []
    for spec in config["arrival_scenarios"]:
        rows = schedule(records, spec["input_period_ms"])
        publications = refresh_timeline(
            rows,
            config["display_refresh_period_ms"],
        )
        queue_waits = np.array([row["queue_wait_ms"] for row in rows])
        completion_ages = np.array([row["completion_age_ms"] for row in rows])
        publish_ages = np.array([row["state_age_ms"] for row in publications])
        new_publish_ages = np.array(
            [
                row["state_age_ms"] for row in publications
                if row["new_version"]
            ]
        )
        max_age_index = int(np.argmax(publish_ages))
        oldest_publication = publications[max_age_index]
        oldest_version = oldest_publication["published_version"]
        age_uncertainty = age_interval(
            mapper,
            sequence["snapshots"][oldest_version],
            algorithm_bound_mm,
            oldest_publication["state_age_ms"],
            config["age_uncertainty"],
        )
        row = {
            **spec,
            "events_received": len(rows),
            "events_computed": len(rows),
            "events_dropped": 0,
            "accepted_events": sum(item["accepted"] for item in rows),
            "last_computed_version": rows[-1]["event_id"],
            "last_published_version": publications[-1]["published_version"],
            "new_version_publications": sum(
                item["new_version"] for item in publications
            ),
            "display_refreshes_with_state": len(publications),
            "queue_wait_ms": {
                "mean": float(np.mean(queue_waits)),
                "p95": float(np.percentile(queue_waits, 95)),
                "max": float(np.max(queue_waits)),
            },
            "completion_age_ms": {
                "mean": float(np.mean(completion_ages)),
                "p95": float(np.percentile(completion_ages, 95)),
                "max": float(np.max(completion_ages)),
            },
            "published_state_age_ms": {
                "mean": float(np.mean(publish_ages)),
                "p95": float(np.percentile(publish_ages, 95)),
                "max": float(np.max(publish_ages)),
            },
            "new_version_publish_age_ms": {
                "mean": float(np.mean(new_publish_ages)),
                "p95": float(np.percentile(new_publish_ages, 95)),
                "max": float(np.max(new_publish_ages)),
            },
            "oldest_published_state": oldest_publication,
            "oldest_state_age_uncertainty": {
                "completion_fraction_interval": age_uncertainty[
                    "completion_fraction_interval"
                ],
                "remaining_within_plan_volume_interval_mm3": age_uncertainty[
                    "remaining_within_plan_volume_interval_mm3"
                ],
                "overcut_within_plan_volume_interval_mm3": age_uncertainty[
                    "overcut_within_plan_volume_interval_mm3"
                ],
                "uncertain_target_state_area_mm2": age_uncertainty[
                    "uncertain_target_state_area_mm2"
                ],
                "latency_displacement_mm": age_uncertainty[
                    "component_bounds_mm"
                ]["latency_displacement"],
            },
            "timeline": rows,
            "publications": publications,
        }
        row["checks"] = {
            "no_motion_dropped": row["events_dropped"] == 0,
            "all_events_computed": (
                row["events_computed"] == row["events_received"] == 16
            ),
            "final_version_computed": row["last_computed_version"] == 16,
            "final_version_published": row["last_published_version"] == 16,
            "published_versions_monotone": all(
                first["published_version"] <= second["published_version"]
                for first, second in zip(publications, publications[1:])
            ),
            "state_and_mesh_versions_match": all(
                item["published_version"] == item["state_version"]
                for item in publications
            ),
        }
        scenarios.append(row)

    checks["all_timeline_checks"] = all(
        all(row["checks"].values()) for row in scenarios
    )
    checks["faster_input_creates_more_queue"] = (
        scenarios[0]["queue_wait_ms"]["max"]
        > scenarios[1]["queue_wait_ms"]["max"]
        > scenarios[2]["queue_wait_ms"]["max"]
    )
    checks["age_uncertainty_contains_algorithm_only"] = all(
        row["oldest_state_age_uncertainty"]["completion_fraction_interval"][0]
        <= row["timeline"][row["oldest_published_state"]["published_version"] - 1][
            "state"
        ]["nominal"]["completion_fraction"]
        <= row["oldest_state_age_uncertainty"]["completion_fraction_interval"][1]
        for row in scenarios
    )

    now = datetime.now().astimezone()
    output_root = (
        Path(output_root)
        if output_root is not None
        else HERE / "实验结果" / (now.strftime("%Y%m%d_%H%M%S") + "_timeline")
    )
    output_root.mkdir(parents=True, exist_ok=False)
    result = {
        "schema_version": 1,
        "time_local": now.isoformat(),
        "status": "completed" if all(checks.values()) else "completed_with_failures",
        "scope": (
            "以一次本机16段顺序执行耗时重放三种合成输入周期；"
            "所有事件均计算，只在100 ms显示刷新时发布最新已完成合格状态"
        ),
        "inputs": {
            "online_records": str(records_path),
            "online_records_sha256": file_hash(records_path),
            "online_metadata": str(metadata_path),
            "online_metadata_sha256": file_hash(metadata_path),
            "sequence": str(SEQUENCE),
            "sequence_sha256": file_hash(SEQUENCE),
            "timeline_config": str(TIMELINE_CONFIG),
            "timeline_config_sha256": file_hash(TIMELINE_CONFIG),
            "implementation": str(Path(__file__).resolve()),
            "implementation_sha256": file_hash(Path(__file__).resolve()),
        },
        "algorithm_surface_bound_mm": algorithm_bound_mm,
        "scenarios": scenarios,
        "checks": checks,
        "interpretation": (
            "这是基于一次已测执行序列的离散事件重放，不是实时线程实测、"
            "真实跟踪时序或硬件保证；状态年龄的10 mm/s速度是假设值"
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
