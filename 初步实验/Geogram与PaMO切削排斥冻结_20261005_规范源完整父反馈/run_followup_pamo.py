"""以同一冻结Geogram终态逐例运行PaMO完整三阶段并保存进程墙钟。"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import subprocess
from time import perf_counter


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--geogram-results", type=Path, required=True)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--example", type=Path, required=True)
    parser.add_argument("--geometry-source", type=Path, required=True)
    parser.add_argument("--variant", choices=("P", "P_plus_S"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument("--limit", type=int, default=6)
    args = parser.parse_args()
    source, python, example, geometry, output = (
        args.geogram_results.resolve(), args.python.resolve(), args.example.resolve(),
        args.geometry_source.resolve(), args.output.resolve())
    if not python.is_file() or not example.is_file() or not geometry.is_file():
        raise FileNotFoundError("PaMO解释器、作者CLI或符号源码不存在")
    expected_geometry_hash = {
        "P": "61553a5740ce71e4458ae39678d99a5a6cd586421884795011b83bc7e3af07b1",
        "P_plus_S": "d92c67cde194385025e2b530d5a443e2878bf848402e2ec72101c543f1cacda3",
    }[args.variant]
    if sha256(geometry) != expected_geometry_hash:
        raise ValueError("符号谓词源码摘要与预声明分支不符")
    if output.exists() and any(output.iterdir()):
        raise ValueError("PaMO输出目录已有文件，禁止覆盖")
    geogram_record = source / "01-Geogram执行记录.json"
    geogram = json.loads(geogram_record.read_text(encoding="utf-8"))
    probe = subprocess.run(
        [str(python), "-c", "import json,pamo,torchcumesh2sdf; print('MODULE_PATHS='+json.dumps([pamo.__file__,torchcumesh2sdf.__file__]))"],
        capture_output=True, text=True, timeout=60, check=False)
    if probe.returncode:
        raise RuntimeError("PaMO或SDF扩展无法从指定解释器导入")
    tagged = [line.removeprefix("MODULE_PATHS=") for line in probe.stdout.splitlines()
              if line.startswith("MODULE_PATHS=")]
    module_paths = [Path(item) for item in json.loads(tagged[-1])] if tagged else []
    if len(module_paths) != 2 or any(not path.is_file() for path in module_paths):
        raise ValueError("PaMO环境探针未返回两个有效模块路径")
    output.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone(timedelta(hours=8)))
    report = {"schema_version": 1, "time_beijing": now.strftime("%Y-%m-%d %H:%M:%S"),
              "variant": args.variant, "geogram_record_sha256": sha256(geogram_record),
              "example_sha256": sha256(example), "geometry_source_sha256": sha256(geometry),
              "loaded_modules": [{"path": str(path), "sha256": sha256(path)} for path in module_paths],
              "ratio": 1.0, "min_vertex": 0,
              "full_stages": True, "rows": []}
    report_path = output / "01-PaMO执行记录.json"
    for row in geogram["routes"][:args.limit]:
        case_id = row["id"]
        if row["status"] != "complete" or not row["final"]:
            report["rows"].append({"id": case_id, "status": "skipped_invalid_geogram"})
            report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            continue
        mesh = source / case_id / row["final"]
        case_output = output / f"{case_id}.obj"
        command = [str(python), str(example), "--input", str(mesh), "--output", str(case_output),
                   "--ratio", "1.0", "--min-vertex", "0"]
        started = perf_counter()
        try:
            completed = subprocess.run(command, capture_output=True, text=True,
                                       timeout=args.timeout_seconds, check=False)
            elapsed = (perf_counter() - started) * 1000
            (output / f"{case_id}.log").write_text(completed.stdout + completed.stderr, encoding="utf-8")
            status = "completed" if completed.returncode == 0 and case_output.is_file() else "failed"
            result = {"id": case_id, "status": status, "returncode": completed.returncode,
                      "process_wall_ms": elapsed, "geogram_sha256": sha256(mesh),
                      "output_sha256": sha256(case_output) if case_output.is_file() else None,
                      "log": f"{case_id}.log"}
        except subprocess.TimeoutExpired as error:
            result = {"id": case_id, "status": "timeout",
                      "process_wall_ms": (perf_counter() - started) * 1000,
                      "geogram_sha256": sha256(mesh)}
        report["rows"].append(result)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(case_id, result["status"], flush=True)


if __name__ == "__main__":
    main()
