"""按冻结合法前缀和参照清单独立审计PaMO开发批次。"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys


HERE = Path(__file__).resolve().parent


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--legal-manifest", type=Path, required=True)
    parser.add_argument("--clean-audits", type=Path, required=True)
    parser.add_argument("--references", type=Path, required=True)
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() and any(args.output.iterdir()):
        raise ValueError("审计输出目录已有文件，禁止覆盖")
    legal = json.loads(args.legal_manifest.read_text(encoding="utf-8"))
    reference_manifest = args.references / "01-参照审计.json"
    references = json.loads(reference_manifest.read_text(encoding="utf-8"))
    run_record = args.runs / "01-PaMO逐前缀执行记录.json"
    runs = json.loads(run_record.read_text(encoding="utf-8"))
    ref_map = {(item["route"], item["event"]): item for item in references["rows"]}
    run_map = {(item["route"], item["event"]): item for item in runs["rows"]}
    if (len(legal["valid"]) != 21 or len(legal["rejected"]) != 3 or
            len(ref_map) != 24 or len(run_map) != 21):
        raise ValueError("开发输入、参照或PaMO运行记录的数量不符")
    args.output.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone(timedelta(hours=8)))
    report = {"schema_version": 2, "time_beijing": now.strftime("%Y-%m-%d %H:%M:%S"),
              "legal_manifest_sha256": sha256(args.legal_manifest),
              "reference_manifest_sha256": sha256(reference_manifest),
              "run_record_sha256": sha256(run_record),
              "variant": runs["variant"], "rows": []}
    report_path = args.output / "01-开发批次独立审计.json"
    for item in legal["valid"]:
        key = item["route"], item["event"]
        row = {"route": key[0], "event": key[1], "status": "audit_failed"}
        report["rows"].append(row)
        run, ref = run_map[key], ref_map[key]
        source = args.clean_audits / key[0] / f"{key[1]}_clean.obj"
        candidate = args.runs / key[0] / f"{key[1]}.obj"
        reference = args.references / ref["mesh"]
        if (run["status"] != "completed" or not candidate.is_file() or
                sha256(candidate) != run["output_sha256"]):
            row["status"] = "execution_invalid"
        elif sha256(source) != item["sha256"] or sha256(reference) != ref["sha256"]:
            row["status"] = "input_or_reference_invalid"
        else:
            case_dir = args.output / key[0]
            case_dir.mkdir(exist_ok=True)
            detail = case_dir / f"{key[1]}_audit.json"
            command = [sys.executable, str(HERE / "audit_followup_candidate.py"),
                       "--source", str(source), "--candidate", str(candidate),
                       "--reference", str(reference), "--reference-sha256", ref["sha256"],
                       "--output", str(detail)]
            completed = subprocess.run(command, capture_output=True, text=True,
                                       timeout=300, check=False)
            if completed.returncode == 0:
                audit = json.loads(detail.read_text(encoding="utf-8"))
                row.update({"status": "audited", "detail": str(detail.relative_to(args.output)),
                            "detail_sha256": sha256(detail),
                            "bad_faces": audit["metrics"]["output_quality"]["bad_faces"],
                            "quality_distribution": audit["quality_distribution"],
                            "legacy_strict_quality_passed": audit["legacy_strict_quality_passed"],
                            "topology_passed": audit["topology_passed_with_vertex_check"],
                            "sampled_max_mm": audit["metrics"]["sampled_reference_geometry"]["sampled_max_mm"],
                            "accepted_under_sampled_protocol":
                                audit["accepted_under_sampled_protocol_with_vertex_check"],
                            "accepted_under_common_budget": None})
            else:
                row["reason"] = completed.stderr[-2000:]
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                               encoding="utf-8")
        print(key[0], key[1], row["status"], flush=True)


if __name__ == "__main__":
    main()
