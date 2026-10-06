"""登记八张已见输入的合法性，打包合法帧，失败帧保留在计分清单。"""

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import shutil
import tarfile
import trimesh

from locality_diagnostic import digest
from preflight_geogram_prefixes import metrics

HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--passes", type=int, choices=(1, 8), default=1)
    parser.add_argument("--ablations", action="store_true")
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    args.output.mkdir(parents=True)
    provenance = HERE / "实验结果/20261004_局部维护来源重放"
    diagnostic = json.loads((provenance / "03-来源三角化对照与局部体检.json").read_text(encoding="utf-8"))
    frozen = HERE / "实验结果/20260928_后续输入冻结_v3"
    parent = json.loads((HERE / "实验结果/20260929_C1试运行准备/01-C1试运行清单.json").read_text(encoding="utf-8"))
    record = {"time_beijing": datetime.now(timezone(timedelta(hours=8))).isoformat(),
              "methods": ["full", "global", "spatial", "boolean"], "rounds": 1,
              "collapse_pass_budget": args.passes,
              "role": "seen_saved_static_inputs_development_not_new_feedback_or_independent_evaluation", "cases": []}
    if args.ablations:
        record["methods"] = ["boolean_no_transition", "boolean_no_boundary"]
        record["role"] += ";boundary_and_transition_ablations"
    for row in diagnostic["rows"]:
        route = next(r for r in parent["routes"] if r["id"] == row["route"])
        source_path = provenance / row["case"] / "no_simplify.obj"
        checks = metrics(trimesh.load(source_path, force="mesh", process=False))
        valid = bool(checks["finite"] and checks["watertight"] and checks["winding_consistent"] and
                     checks["vertex_manifold_closed"] and checks["zero_area_faces"] == 0 and
                     checks["fp32_zero_area_faces"] == 0 and checks["self_intersection_faces"] == 0 and
                     row["source_label_validation"]["passed_1e_8_mm_numerical_check"])
        case = {"case": row["case"], "route": row["route"], "event": row["event"],
                "input_valid": valid, "input_checks": checks, "reference": next(r for r in parent["references"]
                if r["route"] == row["route"] and r["event"] == row["event"])}
        folder = args.output / row["case"]
        folder.mkdir()
        files = {"source.obj": source_path, "labels.json": provenance / row["case"] / "no_simplify.json",
                 "tool.obj": frozen / next(t["mesh"] for t in route["prefix_tools"] if t["event_id"] == row["event"])}
        for name, path in files.items():
            shutil.copy2(path, folder / name)
        case["files_sha256"] = {name: digest(path) for name, path in files.items()}
        record["cases"].append(case)
    names = ("locality_masks.py", "locality_gpu.py", "run_locality_gpu_pilot.py", "run_locality_saved_batch.py")
    record["code_sha256"] = {}
    for name in names:
        shutil.copy2(HERE / name, args.output / name)
        record["code_sha256"][name] = digest(args.output / name)
    (args.output / "01-保存帧开发批次.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with tarfile.open(args.output / "locality_saved_batch.tar.gz", "w:gz") as archive:
        for path in sorted(args.output.rglob("*")):
            if path.is_file() and path.suffix != ".gz":
                archive.add(path, arcname=str(path.relative_to(args.output)).replace("\\", "/"))
    print("八帧均已登记，合法帧", sum(c["input_valid"] for c in record["cases"]))


if __name__ == "__main__":
    main()
