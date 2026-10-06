"""执行保存帧开发对照；实际输入哈希与合法性不符时拒绝运行。"""

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from time import perf_counter


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--extension", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    manifest_path = args.inputs / "01-保存帧开发批次.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for name, sha in manifest["code_sha256"].items():
        if digest(args.inputs / name) != sha:
            raise ValueError("批次源码摘要不符: " + name)
    args.output.mkdir(parents=True)
    report = {"time_beijing": datetime.now(timezone(timedelta(hours=8))).isoformat(),
              "manifest_sha256": digest(manifest_path), "cases": []}
    for case in manifest["cases"]:
        row = {"case": case["case"], "route": case["route"], "event": case["event"]}
        for name, sha in case["files_sha256"].items():
            if digest(args.inputs / case["case"] / name) != sha:
                raise ValueError("批次输入摘要不符: " + case["case"] + "/" + name)
        if not case["input_valid"]:
            row["status"] = "input_rejected"
        else:
            folder = args.inputs / case["case"]
            start = perf_counter()
            with (args.output / (case["case"] + ".log")).open("w") as log:
                command = [sys.executable, str(args.inputs / "run_locality_gpu_pilot.py"),
                           "--source", str(folder / "source.obj"), "--labels", str(folder / "labels.json"),
                           "--tool", str(folder / "tool.obj"), "--extension", str(args.extension),
                           "--output", str(args.output / case["case"]), "--rounds", str(manifest["rounds"]),
                           "--methods", *manifest["methods"]]
                try:
                    rc = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=3700, check=False).returncode
                except subprocess.TimeoutExpired:
                    rc = 124
            row.update(status="pending_independent_audit" if rc == 0 else "execution_failed", returncode=rc,
                       batch_case_including_import_wall_ms=(perf_counter() - start) * 1000)
        report["cases"].append(row)
        (args.output / "01-开发执行汇总.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(row, flush=True)
    report["status"] = "execution_completed_audit_pending"
    (args.output / "01-开发执行汇总.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
