"""从冻结原初态重放指定事件的完整工具前缀，验证逐步参照机制。"""
import argparse
import json
from pathlib import Path
from audit_followup_candidate import sha256
from guarded_reference_recovery import recover_reference
from run_constrained_batch import RemoteQuality
from run_geometry_study import execute, save, now


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--route", required=True)
    parser.add_argument("--event", required=True)
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    manifest_path = args.prepared/"01-完整范围冻结清单.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    route = next(r for r in manifest["routes"] if r["id"] == args.route)
    args.output.mkdir(exist_ok=False)
    engine = RemoteQuality(args.output, args.port)
    try:
        if execute(engine.client, ["mkdir", engine.remote])["returncode"]:
            raise RuntimeError("独立诊断目录已存在")
        mesh, record = recover_reference(engine, args.prepared, route, args.event, None,
            args.output/"replay", False)
        save(args.output/"01-逐步参照完整前缀诊断.json", dict(time_beijing=now(),
            manifest_sha256=sha256(manifest_path), record=record,
            mechanism_sha256=sha256(Path(__file__).with_name("guarded_reference_recovery.py")),
            scope="独立参照诊断，不运行候选、不发布、不修改既有完整分母"))
        print("accepted", record["accepted"], "steps", len(record["steps"]), "status", record["status"])
    finally:
        engine.close()
