"""打包固定PaMO源码和同批Geogram闭合输出，供NVIDIA远端运行。"""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PAMO = ROOT / "reference/近期强基线_20260908/pamo"
PAMO_COMMIT = "a10e34351eb7de71f41eb279e7ab9b2b101cf7a4"


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def tracked_files(repository):
    output = subprocess.check_output(
        ["git", "-C", str(repository), "ls-files", "-z"]
    )
    return [name for name in output.decode().split("\0") if name]


def add_bytes(bundle, name, content, mode=0o644):
    info = tarfile.TarInfo(name)
    info.size = len(content)
    info.mode = mode
    bundle.addfile(info, io.BytesIO(content))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("experiment", type=Path)
    args = parser.parse_args()

    experiment = args.experiment.resolve()
    result_path = experiment / "results.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if result.get("status") != "completed":
        raise RuntimeError("只打包已完整执行的共同实验结果")

    commit = subprocess.check_output(
        ["git", "-C", str(PAMO), "rev-parse", "HEAD"],
        text=True,
    ).strip()
    if commit != PAMO_COMMIT:
        raise RuntimeError(f"PaMO提交不匹配: {commit}")
    if subprocess.check_output(
        ["git", "-C", str(PAMO), "status", "--short"],
        text=True,
    ):
        raise RuntimeError("PaMO作者工作区必须无修改")

    now = datetime.now(timezone(timedelta(hours=8)))
    output = (
        HERE
        / "实验结果"
        / (now.strftime("%Y%m%d_%H%M%S") + "_pamo_prepared")
    )
    output.mkdir(parents=True, exist_ok=False)
    archive = output / "pamo_remote_bundle.tar.gz"
    inputs = []

    with tarfile.open(archive, "w:gz") as bundle:
        for name in tracked_files(PAMO):
            source = PAMO / name
            if source.is_file():
                bundle.add(source, arcname=f"pamo/{name}", recursive=False)
        warp = PAMO / "simp_cuda/safe_project/warp_"
        for name in tracked_files(warp):
            source = warp / name
            if source.is_file():
                bundle.add(
                    source,
                    arcname=f"pamo/simp_cuda/safe_project/warp_/{name}",
                    recursive=False,
                )

        for row in result["quality_failure_challenge"]["cases"]:
            case_id = row["case_id"]
            diagnostics = row["methods"]["geogram_exact_csg"]["diagnostics"]
            final_name = diagnostics["steps"][-1]["output"]
            source = experiment / f"{case_id}_geogram_work" / final_name
            if not source.is_file():
                raise FileNotFoundError(source)
            target_name = f"{case_id}.obj"
            bundle.add(source, arcname=f"inputs/{target_name}", recursive=False)
            inputs.append(
                {
                    "case_id": case_id,
                    "source": str(source),
                    "archive_path": f"inputs/{target_name}",
                    "sha256": file_hash(source),
                }
            )

        for path in (HERE / "run_pamo_author.py", HERE / "run_pamo_remote.sh"):
            bundle.add(path, arcname=path.name, recursive=False)

        embedded_manifest = {
            "schema_version": 1,
            "time_beijing": now.strftime("%Y-%m-%d %H:%M:%S"),
            "source_experiment": str(experiment),
            "source_results_sha256": file_hash(result_path),
            "pamo_repository": "https://github.com/SarahWeiii/pamo",
            "pamo_commit": PAMO_COMMIT,
            "pamo_license": "AGPL-3.0",
            "pamo_warp_commit": subprocess.check_output(
                ["git", "-C", str(warp), "rev-parse", "HEAD"],
                text=True,
            ).strip(),
            "parameters": {
                "ratio": 1.0,
                "min_vertices": 0,
                "stage1_enabled": True,
                "stage2_enabled": True,
                "stage3_enabled": True,
            },
            "inputs": inputs,
        }
        add_bytes(
            bundle,
            "manifest.json",
            json.dumps(
                embedded_manifest,
                ensure_ascii=False,
                indent=2,
            ).encode("utf-8"),
        )

    local_manifest = {
        **embedded_manifest,
        "archive": archive.name,
        "archive_sha256": file_hash(archive),
        "status": "prepared_not_executed",
        "remote_command": "bash run_pamo_remote.sh all",
    }
    (output / "manifest.json").write_text(
        json.dumps(local_manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(output)


if __name__ == "__main__":
    main()
