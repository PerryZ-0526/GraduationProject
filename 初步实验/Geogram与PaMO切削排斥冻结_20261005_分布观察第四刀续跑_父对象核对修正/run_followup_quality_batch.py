"""对冻结开发前缀的完整PaMO输出批量运行自动质量机制。"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys


HERE = Path(__file__).resolve().parent
QUALITY = HERE / "auto_quality_q.py"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--legal-manifest", type=Path, required=True)
    parser.add_argument("--clean-audits", type=Path, required=True)
    parser.add_argument("--pamo", type=Path, required=True)
    parser.add_argument("--mode", choices=("Q", "Q_minus"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() and any(args.output.iterdir()):
        raise ValueError("质量批次输出目录已有文件，禁止覆盖")
    legal = json.loads(args.legal_manifest.read_text(encoding="utf-8"))
    run_record = args.pamo / "01-PaMO逐前缀执行记录.json"
    pamo = json.loads(run_record.read_text(encoding="utf-8"))
    run_map = {(row["route"], row["event"]): row for row in pamo["rows"]}
    if len(legal["valid"]) != 21 or len(legal["rejected"]) != 3 or len(run_map) != 21:
        raise ValueError("开发前缀覆盖不完整")
    args.output.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone(timedelta(hours=8)))
    report = {"schema_version": 1, "time_beijing": now.strftime("%Y-%m-%d %H:%M:%S"),
              "mode": args.mode, "pamo_variant": pamo["variant"],
              "legal_manifest_sha256": sha256(args.legal_manifest),
              "pamo_run_record_sha256": sha256(run_record),
              "quality_code_sha256": sha256(QUALITY),
              "upstream_rejected": legal["rejected"], "rows": []}
    report_path = args.output / "01-自动质量开发批次.json"
    for item in legal["valid"]:
        route, event = item["route"], item["event"]
        source = args.clean_audits / route / f"{event}_clean.obj"
        candidate = args.pamo / route / f"{event}.obj"
        row = {"route": route, "event": event, "status": "failed"}
        report["rows"].append(row)
        if (sha256(source) != item["sha256"] or
                sha256(candidate) != run_map[(route, event)]["output_sha256"]):
            row["status"] = "input_invalid"
        else:
            case_dir = args.output / route
            case_dir.mkdir(exist_ok=True)
            output = case_dir / f"{event}.obj"
            detail = case_dir / f"{event}_diagnostics.json"
            command = [sys.executable, str(QUALITY), "--source", str(source),
                       "--pamo", str(candidate), "--output", str(output),
                       "--diagnostics", str(detail)]
            if args.mode == "Q_minus":
                command.append("--without-source")
            try:
                completed = subprocess.run(command, capture_output=True, text=True,
                                           timeout=600, check=False)
                if completed.returncode == 0 and output.is_file() and detail.is_file():
                    diagnostics = json.loads(detail.read_text(encoding="utf-8"))
                    row.update({"status": diagnostics["status"],
                                "initial_bad_faces": diagnostics.get("initial_bad_faces"),
                                "final_bad_faces": diagnostics.get("final_bad_faces"),
                                "accepted_operations": len(diagnostics["accepted"]),
                                "quality_wall_ms": diagnostics.get("elapsed_ms"),
                                "candidate_sha256": sha256(output),
                                "diagnostics_sha256": sha256(detail)})
                else:
                    row["reason"] = (completed.stdout + completed.stderr)[-2000:]
            except subprocess.TimeoutExpired:
                row["status"] = "timeout"
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                               encoding="utf-8")
        print(route, event, row["status"], row.get("final_bad_faces"), flush=True)


if __name__ == "__main__":
    main()
