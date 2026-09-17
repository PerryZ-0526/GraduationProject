"""加密复核高度图适用域，量化规则采样漏掉的窄小内部区间。"""
from datetime import datetime
import hashlib
import json
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

from motion_record import load_document, replay_case
from surface_methods import top_connected_height


HERE = Path(__file__).resolve().parent
SPACINGS_MM = (0.025, 0.0125, 0.00625, 0.005, 0.003125, 0.0025)
CASE_SPECS = (
    ("quality_development_cases_v3.json", 391),
    ("quality_failure_cases_v2.json", 356),
    ("vertical_wall_development_cases_v1.json", 243),
    ("vertical_wall_development_cases_v1.json", 331),
)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def cavity_count(case, replay, spacing):
    sample_count = int(round(4.0 / spacing)) + 1
    axis = np.linspace(-2.0, 2.0, sample_count)
    count = 0
    for x_chunk in np.array_split(axis, 32):
        xy = np.stack(
            np.meshgrid(x_chunk, axis, indexing="ij"),
            axis=-1,
        )
        _, _, diagnostics = top_connected_height(xy, case, replay)
        count += diagnostics["internal_cavity_sample_count"]
    return {
        "spacing_mm": spacing,
        "axis_samples": sample_count,
        "sample_count": sample_count**2,
        "internal_cavity_sample_count": count,
        "all_removed_intervals_top_connected": count == 0,
    }


def main():
    rows = []
    input_hashes = {}
    for filename, generation_index in CASE_SPECS:
        path = HERE / filename
        input_hashes[filename] = sha256(path)
        document = load_document(path)
        case = next(
            case
            for case in document["cases"]
            if case["screening_generation_index"] == generation_index
        )
        replay = replay_case(case, document["replay_policy"])
        checks = [
            cavity_count(case, replay, spacing)
            for spacing in SPACINGS_MM
        ]
        first_detected = next(
            (
                row["spacing_mm"]
                for row in checks
                if row["internal_cavity_sample_count"] > 0
            ),
            None,
        )
        rows.append(
            {
                "case_id": case["id"],
                "screening_generation_index": generation_index,
                "checks": checks,
                "first_tested_spacing_with_detection_mm": first_detected,
            }
        )
        print(case["id"], first_detected, flush=True)

    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    output = (
        HERE
        / "实验结果"
        / f"{now.strftime('%Y%m%d_%H%M%S')}_non_single_value_scope"
    )
    output.mkdir(parents=True, exist_ok=False)
    result = {
        "schema_version": 1,
        "time_beijing": now.isoformat(),
        "record_kind": "simulated",
        "input_sha256": input_hashes,
        "spacings_mm": list(SPACINGS_MM),
        "cases": rows,
        "summary": {
            "case_count": len(rows),
            "missed_at_0_025_mm": sum(
                row["checks"][0]["internal_cavity_sample_count"] == 0
                and any(
                    check["internal_cavity_sample_count"] > 0
                    for check in row["checks"][1:]
                )
                for row in rows
            ),
            "interpretation": (
                "规则点采样未命中不构成连续适用域证书；来源切换的"
                "单侧高度跳变可作为更敏感的非单值拒绝信号"
            ),
        },
    }
    path = output / "results.json"
    path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(output)


if __name__ == "__main__":
    main()
