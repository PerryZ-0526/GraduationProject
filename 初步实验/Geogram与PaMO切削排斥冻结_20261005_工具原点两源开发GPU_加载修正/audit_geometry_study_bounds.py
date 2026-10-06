"""对连续体检中各分支最后有效网格追加离散曲面数值距离区间。"""

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import trimesh
import pyvista as pv

from geometry_preservation_audit import directed_interval
from audit_pamo_outputs import as_polydata
from audit_followup_candidate import sha256


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    record = args.runs / "01-连续几何执行与审计.json"
    report = json.loads(record.read_text(encoding="utf-8"))
    final = {}
    for row in report["rows"]:
        if row["status"] == "accepted_sampled":
            final[row["route"], row["branch"]] = row
    result = {"time_beijing": datetime.now(timezone(timedelta(hours=8))).isoformat(),
              "run_record_sha256": sha256(record), "rows": []}
    reference_root = Path(__file__).resolve().parent / "实验结果/20260928_独立解析参照"
    analytic_rows = json.loads((reference_root / "01-参照审计.json").read_text(encoding="utf-8"))["rows"]
    analytic = {(r["route"], r["event"]): r for r in analytic_rows}
    for (route, branch), row in final.items():
        folder = args.runs / route / row["event"]
        reference_path = folder / "R.obj"
        # 累计工具参照被报警阻断时，解析路线仍可复核已冻结的独立离散参照。
        reference_kind = "cumulative_discrete_tools"
        if not reference_path.is_file() or "to_cumulative_reference" not in row:
            ref = analytic.get((route, row["event"]))
            if ref is None:
                continue
            reference_path = reference_root / ref["mesh"]
            if sha256(reference_path) != ref["sha256"]:
                raise ValueError("独立参照摘要变化")
            reference_kind = "analytic_field_discrete_isosurface"
        candidate_path = folder / (branch + "_pamo.obj")
        candidate = as_polydata(trimesh.load(candidate_path, force="mesh", process=False))
        reference = pv.read(reference_path) if reference_path.suffix == ".vtp" else as_polydata(
            trimesh.load(reference_path, force="mesh", process=True, validate=True))
        forward = directed_interval(candidate, reference)
        reverse = directed_interval(reference, candidate)
        result["rows"].append({"route": route, "branch": branch, "event": row["event"],
            "reference_kind": reference_kind,
            "candidate_sha256": sha256(candidate_path), "reference_sha256": sha256(reference_path),
            "forward": forward, "reverse": reverse,
            "lower_mm": max(forward["lower_mm"], reverse["lower_mm"]),
            "upper_mm": max(forward["upper_mm"], reverse["upper_mm"]),
            "certified_continuous_geometry": False})
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(route, branch, row["event"], round(result["rows"][-1]["upper_mm"], 5), flush=True)


if __name__ == "__main__":
    main()
