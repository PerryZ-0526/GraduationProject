"""核验首张开发输入后生成局部维护试跑包，不含配置或凭据。"""

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import shutil
import tarfile
import trimesh

from preflight_geogram_prefixes import metrics

HERE = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    provenance = HERE / "实验结果/20261004_局部维护来源重放/crossing_e0"
    frozen = HERE / "实验结果/20260928_后续输入冻结_v3"
    source = trimesh.load(provenance / "no_simplify.obj", force="mesh", process=False)
    checks = metrics(source)
    if not (checks["finite"] and checks["watertight"] and checks["winding_consistent"] and checks["vertex_manifold_closed"]
            and checks["zero_area_faces"] == 0 and checks["fp32_zero_area_faces"] == 0 and checks["self_intersection_faces"] == 0):
        raise ValueError("首张输入未通过共同门控")
    args.output.mkdir(parents=True)
    files = {"source.obj": provenance / "no_simplify.obj", "labels.json": provenance / "no_simplify.json",
             "tool.obj": frozen / "development_crossing_slab_01_e0_tool.obj"}
    for name in ("locality_masks.py", "locality_gpu.py", "run_locality_gpu_pilot.py"):
        files[name] = HERE / name
    for name, source_path in files.items():
        shutil.copy2(source_path, args.output / name)
    record = {"time_beijing": datetime.now(timezone(timedelta(hours=8))).isoformat(),
              "case": "development_crossing_slab_01/e0", "input_checks": checks,
              "files_sha256": {name: digest(path) for name, path in files.items()},
              "methods": ["full", "global", "spatial", "boolean"], "rounds": 1,
              "role": "implementation_pilot_not_performance_evaluation"}
    (args.output / "01-首帧试跑冻结.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with tarfile.open(args.output / "locality_pilot.tar.gz", "w:gz") as archive:
        for name in files:
            archive.add(args.output / name, arcname=name)
    print("首帧输入及代码摘要已冻结")


if __name__ == "__main__":
    main()
