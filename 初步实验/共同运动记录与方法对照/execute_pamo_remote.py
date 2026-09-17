"""上传已冻结PaMO包、运行作者CLI并回收审计结果。"""
import argparse
from datetime import datetime
import json
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
    args = parser.parse_args()

    prepared = args.prepared.resolve()
    manifest = json.loads(
        (prepared / "manifest.json").read_text(encoding="utf-8")
    )
    archive = prepared / manifest["archive"]
    attempt_path = prepared / "remote_attempt.json"
    attempt = {
        "schema_version": 1,
        "time_local": datetime.now().astimezone().isoformat(),
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
    if not (ROOT / ".env").is_file():
        attempt.update(
            {
                "status": "blocked_missing_connection_config",
                "reason": (
                    "既有remote.py要求项目根目录.env包含CUDA_SSH_HOST、"
                    "CUDA_SSH_PORT、CUDA_SSH_USER和CUDA_SSH_PASSWORD"
                ),
            }
        )
        save()
        print(attempt_path)
        return 2

    remote = (
        "/root/autodl-tmp/graduation_project/pamo_quality_"
        + prepared.name.split("_pamo_prepared")[0]
    )

    def connect(name, arguments, timeout=900):
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
        )
        content = re.sub(
            r"Unable to connect to port [^\r\n]+",
            "Unable to connect to configured SSH endpoint",
            completed.stdout + completed.stderr,
        )
        log = prepared / f"{name}.log"
        log.write_text(content, encoding="utf-8")
        attempt["steps"].append(
            {
                "name": name,
                "arguments": arguments,
                "exit_code": completed.returncode,
                "log": log.name,
            }
        )
        save()
        print(name, completed.returncode, content[-2000:], flush=True)
        return completed.returncode

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
        f"sha256sum {shlex.quote(archive.name)} && "
        f"tar -xzf {shlex.quote(archive.name)}"
    )
    if connect("03_unpack", ["--command", unpack]):
        attempt["status"] = "unpack_failed"
        save()
        return 1

    run = (
        f"cd {shlex.quote(remote)}; "
        "bash run_pamo_remote.sh all > run.log 2>&1; rc=$?; "
        "cat run.log; "
        "tar -czf remote_artifacts.tar.gz run.log outputs 2>/dev/null || "
        "tar -czf remote_artifacts.tar.gz run.log; "
        "exit $rc"
    )
    run_code = connect("04_run", ["--command", run], timeout=7200)
    local_archive = prepared / "remote_artifacts.tar.gz"
    get_code = connect(
        "05_download",
        ["--get", f"{remote}/remote_artifacts.tar.gz", str(local_archive)],
        timeout=1800,
    )
    if get_code:
        attempt["status"] = "download_failed"
        save()
        return 1

    extracted = prepared / "remote_artifacts"
    extracted.mkdir(exist_ok=False)
    with tarfile.open(local_archive, "r:gz") as bundle:
        bundle.extractall(extracted, filter="data")
    output_dir = extracted / "outputs"
    remote_results = output_dir / "remote_results.json"
    if run_code or not remote_results.is_file():
        attempt["status"] = "remote_run_failed"
        save()
        return 1

    audit = subprocess.run(
        [
            sys.executable,
            "-B",
            "-X",
            "utf8",
            str(AUDITOR),
            manifest["source_experiment"],
            str(output_dir),
        ],
        capture_output=True,
        text=True,
        timeout=1800,
        check=False,
    )
    audit_log = prepared / "06_audit.log"
    audit_log.write_text(audit.stdout + audit.stderr, encoding="utf-8")
    attempt["steps"].append(
        {
            "name": "06_audit",
            "exit_code": audit.returncode,
            "log": audit_log.name,
        }
    )
    attempt["status"] = "completed" if audit.returncode == 0 else "audit_failed"
    save()
    print(audit.stdout, audit.stderr, sep="", flush=True)
    return audit.returncode


if __name__ == "__main__":
    raise SystemExit(main())
