"""上传已冻结PaMO包、运行作者CLI并回收审计结果。"""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tarfile


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
REMOTE_HELPER = ROOT / "初步实验/CUDA远程验证/remote.py"
AUDITOR = HERE / "audit_pamo_outputs.py"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("prepared", type=Path)
    parser.add_argument("--connection-config", type=Path, default=ROOT / ".env")
    args = parser.parse_args()

    prepared = args.prepared.resolve()
    manifest = json.loads(
        (prepared / "manifest.json").read_text(encoding="utf-8")
    )
    archive = prepared / manifest["archive"]
    if hashlib.sha256(archive.read_bytes()).hexdigest() != manifest["archive_sha256"]:
        raise RuntimeError("本地压缩包摘要与manifest不一致")
    now = datetime.now(timezone(timedelta(hours=8)))
    attempt_dir = prepared / "attempts" / now.strftime("%Y%m%d_%H%M%S_%f")
    attempt_dir.mkdir(parents=True, exist_ok=False)
    attempt_path = attempt_dir / "remote_attempt.json"
    attempt = {
        "schema_version": 1,
        "time_beijing": now.strftime("%Y-%m-%d %H:%M:%S"),
        "status": "running",
        "prepared_manifest": str(prepared / "manifest.json"),
        "archive_sha256": manifest["archive_sha256"],
        "steps": [],
    }

    def save():
        attempt_path.write_text(
            json.dumps(attempt, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    save()
    connection_config = args.connection_config.resolve()
    if not connection_config.is_file():
        attempt.update(
            {
                "status": "blocked_missing_connection_config",
                "reason": (
                    "远端配置需要CUDA_SSH_HOST、"
                    "CUDA_SSH_PORT、CUDA_SSH_USER和CUDA_SSH_PASSWORD"
                ),
            }
        )
        save()
        print(attempt_path)
        return 2

    config = dict(
        line.split("=", 1)
        for line in connection_config.read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#") and "=" in line
    )
    remote_root = config.get("CUDA_REMOTE_ROOT", "/root/autodl-tmp/graduation_project")
    remote = remote_root.rstrip("/") + "/pamo_quality_" + attempt_dir.name

    def connect(name, arguments, timeout=900):
        try:
            completed = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    "-X",
                    "utf8",
                    str(REMOTE_HELPER),
                    "--timeout",
                    str(timeout),
                    *arguments,
                ],
                capture_output=True,
                text=True,
                timeout=timeout + 60,
                check=False,
                env={**os.environ, "CUDA_CONFIG_FILE": str(connection_config)},
            )
            exit_code = completed.returncode
            raw_content = completed.stdout + completed.stderr
        except subprocess.TimeoutExpired as error:
            exit_code = 124
            raw_content = str(error)
        content = re.sub(
            r"Unable to connect to port [^\r\n]+",
            "Unable to connect to configured SSH endpoint",
            raw_content,
        )
        log = attempt_dir / f"{name}.log"
        log.write_text(content, encoding="utf-8")
        attempt["steps"].append(
            {
                "name": name,
                "arguments": arguments,
                "exit_code": exit_code,
                "log": log.name,
            }
        )
        save()
        print(name, exit_code, content[-2000:], flush=True)
        return exit_code

    if connect("01_create", ["--command", f"mkdir -p {shlex.quote(remote)}"]):
        attempt["status"] = "connection_or_remote_create_failed"
        save()
        return 1
    if connect(
        "02_upload",
        ["--put", str(archive), f"{remote}/{archive.name}"],
        timeout=1800,
    ):
        attempt["status"] = "upload_failed"
        save()
        return 1
    unpack = (
        f"cd {shlex.quote(remote)} && "
        f"printf '%s  %s\\n' {shlex.quote(manifest['archive_sha256'])} {shlex.quote(archive.name)} | sha256sum -c - && "
        f"tar -xzf {shlex.quote(archive.name)}"
    )
    if connect("03_unpack", ["--command", unpack]):
        attempt["status"] = "unpack_failed"
        save()
        return 1

    run = (
        f"cd {shlex.quote(remote)}; "
        "bash run_pamo_remote.sh environment > environment.log 2>&1 && "
        "bash run_pamo_remote.sh setup > setup.log 2>&1 && "
        "venv/bin/python pamo/example.py --input pamo/mesh/BirdHouse_B019SXLRJ2_MetalLeafRoofGreenWalls_TU.obj "
        "--output author_example.obj --ratio 0.001 > author_example.log 2>&1 && "
        "bash run_pamo_remote.sh run > run.log 2>&1; rc=$?; "
        "tar -czf remote_artifacts.tar.gz environment.log setup.log author_example.log "
        "author_example.obj run.log dependencies.txt outputs 2>/dev/null || "
        "tar -czf remote_artifacts.tar.gz --ignore-failed-read environment.log setup.log "
        "author_example.log author_example.obj run.log dependencies.txt outputs 2>/dev/null; "
        "exit $rc"
    )
    run_code = connect("04_run", ["--command", run], timeout=7200)
    local_archive = attempt_dir / "remote_artifacts.tar.gz"
    get_code = connect(
        "05_download",
        ["--get", f"{remote}/remote_artifacts.tar.gz", str(local_archive)],
        timeout=1800,
    )
    if get_code:
        attempt["status"] = "download_failed"
        save()
        return 1

    extracted = attempt_dir / "remote_artifacts"
    extracted.mkdir(exist_ok=False)
    with tarfile.open(local_archive, "r:gz") as bundle:
        bundle.extractall(extracted, filter="data")
    output_dir = extracted / "outputs"
    remote_results = output_dir / "remote_results.json"
    if remote_results.is_file():
        audit = subprocess.run(
            [sys.executable, "-B", "-X", "utf8", str(AUDITOR),
             str(prepared / "manifest.json"), str(output_dir)],
            capture_output=True, text=True, timeout=1800, check=False,
        )
        audit_log = attempt_dir / "06_audit.log"
        audit_log.write_text(audit.stdout + audit.stderr, encoding="utf-8")
        attempt["steps"].append(
            {"name": "06_audit", "exit_code": audit.returncode, "log": audit_log.name}
        )
        attempt["status"] = "completed" if run_code == 0 and audit.returncode == 0 else "completed_with_failures"
    else:
        attempt["status"] = "remote_run_failed_no_results"
    save()
    if remote_results.is_file():
        print(audit.stdout, audit.stderr, sep="", flush=True)
    return 0 if attempt["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
