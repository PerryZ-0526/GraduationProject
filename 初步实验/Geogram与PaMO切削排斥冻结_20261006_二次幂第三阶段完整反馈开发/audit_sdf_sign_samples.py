"""用源网格的射线包含与实体角审计固定 SDF 节点样本。"""

import argparse
import json
from pathlib import Path

import numpy as np
import trimesh

from input_winding_audit import winding_numbers


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--samples", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    source = trimesh.load(args.input, force="mesh", process=False)
    record = json.loads(args.samples.read_text(encoding="utf-8"))
    samples = record["samples"]
    points = np.asarray([row["point_mm"] for row in samples], dtype=np.float64)
    signed = np.asarray([row["sdf"] for row in samples], dtype=np.float64)
    rays = source.contains(points)
    winding = winding_numbers(source, points)
    winding_inside = np.abs(winding) > 0.5
    groups = {}
    for group in sorted({row["group"] for row in samples}):
        selected = np.asarray([row["group"] == group for row in samples])
        disagreement = selected & (rays != winding_inside)
        sign_mismatch = selected & (rays != (signed < 0))
        groups[group] = {
            "count": int(selected.sum()),
            "ray_winding_disagreements": int(disagreement.sum()),
            "sdf_ray_sign_mismatches": int(sign_mismatch.sum()),
            "mismatch_examples": [
                {"grid": samples[index]["grid"],
                 "sdf": float(signed[index]),
                 "winding": float(winding[index]),
                 "ray_inside": bool(rays[index])}
                for index in np.flatnonzero(sign_mismatch)[:5]
            ],
        }
    result = {
        "input": args.input.name,
        "groups": groups,
        "interpretation": "有限固定样本核查，不构成全部体素或连续实体的符号证书",
    }
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
