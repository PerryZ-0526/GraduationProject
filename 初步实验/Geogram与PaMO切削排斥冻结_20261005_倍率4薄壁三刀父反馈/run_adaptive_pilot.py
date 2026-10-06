"""新接缝机制开发对照，沿用完整安全投影并独立重审输出。"""

import argparse
import json
from pathlib import Path
import trimesh
from run_constrained_batch import RemoteQuality, HERE
from run_constrained_feedback import global_geometry
from run_geometry_study import save, now
from geometry_preservation_audit import mesh_valid
from audit_followup_candidate import sha256, quality_distribution


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--port", required=True, type=int)
    parser.add_argument("--limit", type=int, default=2)
    parser.add_argument("--methods", nargs="+", choices=("full", "adaptive", "adaptive_planar"), default=["full", "adaptive", "adaptive_planar"])
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    report = {"time_beijing": now(), "status": "running", "scope": "已见保存帧机制开发，不是独立或连续反馈", "rows": []}
    engine = RemoteQuality(args.output, args.port)
    try:
        report["environment"] = engine.setup()
        # 新脚本只覆盖本次隔离目录的入口，旧冻结源码与二进制保持原样。
        for name in ("adaptive_seam.py", "run_adaptive_worker.py", "planar_quality.py", "locality_retriangulate.py"):
            engine.sftp.put(str(HERE / name), engine.remote + "/" + name)
            (args.output / name).write_bytes((HERE / name).read_bytes())
        engine.sftp.put(str(HERE / "run_adaptive_worker.py"), engine.remote + "/run_constrained_worker.py")
        report["new_code_sha256"] = {name: sha256(HERE / name) for name in ("adaptive_seam.py", "run_adaptive_worker.py", "planar_quality.py", "locality_retriangulate.py")}
        prepared = HERE / "实验结果/20261004_局部维护保存帧开发"
        cases = json.loads((prepared / "01-保存帧开发批次.json").read_text(encoding="utf-8"))["cases"][:args.limit]
        save(args.output / "01-开发记录.json", report)
        for case in cases:
            inputs = prepared / case["case"]
            source = trimesh.load(inputs / "source.obj", force="mesh", process=False)
            for method in args.methods:
                folder = args.output / (case["case"] + "_" + method)
                row = engine.run(inputs / "source.obj", inputs / "labels.json", inputs / "tool.obj", method, folder)
                row["case"] = case["case"]
                if row["execution"]["returncode"] == 0:
                    candidate = trimesh.load(folder / "candidate.obj", force="mesh", process=False)
                    valid, metrics = mesh_valid(candidate)
                    geometry = global_geometry(candidate, source)
                    log = (folder / "worker.log").read_text(encoding="utf-8")
                    capacity = "exceeds max_blocks" in log or "Number of contacts" in log
                    same_topology = candidate.euler_number == source.euler_number and len(candidate.split(only_watertight=False)) == len(source.split(only_watertight=False))
                    row.update(output_metrics=metrics, geometry=geometry, quality=quality_distribution(candidate),
                               source_quality=quality_distribution(source), capacity_alarm=capacity,
                               status="accepted_numeric_audit" if valid and same_topology and geometry["probe_max_mm"] <= .1 and not capacity else "audit_rejected")
                report["rows"].append(row)
                save(args.output / "01-开发记录.json", report)
                print(case["case"], method, row["status"], flush=True)
        report["status"] = "completed_with_recorded_failures"
        save(args.output / "01-开发记录.json", report)
    finally:
        engine.close()


if __name__ == "__main__":
    main()
