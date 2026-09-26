"""打包固定PaMO源码和同批Geogram闭合输出，供NVIDIA远端运行。"""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import tarfile


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PAMO = ROOT / "reference/近期强基线_20260908/pamo"
PAMO_COMMIT = "a10e34351eb7de71f41eb279e7ab9b2b101cf7a4"
WARP_COMMIT = "fd17b8594a2f95f500884ff3d87904d776750897"


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


def selected_inputs(experiment, inputs_manifest):
    if inputs_manifest is not None:
        document = json.loads(inputs_manifest.read_text(encoding="utf-8"))
        rows = document["inputs"]
        selected = []
        for row in rows:
            source = Path(row["path"])
            if not source.is_absolute():
                source = inputs_manifest.parent / source
            selected.append((row["case_id"], source.resolve(), row["sha256"]))
    else:
        result_path = experiment / "results.json"
        result = json.loads(result_path.read_text(encoding="utf-8"))
        if result.get("status") != "completed":
            raise RuntimeError("只打包已完整执行的共同实验结果")
        selected = []
        for row in result["quality_failure_challenge"]["cases"]:
            case_id = row["case_id"]
            steps = row["methods"]["geogram_exact_csg"]["diagnostics"]["steps"]
            source = experiment / f"{case_id}_geogram_work" / steps[-1]["output"]
            selected.append((case_id, source, None))
    if not selected:
        raise ValueError("输入清单为空")
    case_ids = set()
    for case_id, source, expected_hash in selected:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", case_id) or case_id in case_ids:
            raise ValueError(f"案例编号非法或重复: {case_id}")
        case_ids.add(case_id)
        if source.suffix.lower() != ".obj" or not source.is_file():
            raise FileNotFoundError(source)
        if expected_hash is not None and file_hash(source) != expected_hash.lower():
            raise ValueError(f"输入摘要不匹配: {case_id}")
    return selected


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("experiment", type=Path, nargs="?")
    parser.add_argument("--inputs-manifest", type=Path)
    parser.add_argument("--reference-manifest", type=Path)
    args = parser.parse_args()
    if (args.experiment is None) == (args.inputs_manifest is None):
        parser.error("必须且只能提供旧实验目录或--inputs-manifest")

    experiment = args.experiment.resolve() if args.experiment else None
    inputs_manifest = args.inputs_manifest.resolve() if args.inputs_manifest else None
    selected = selected_inputs(experiment, inputs_manifest)
    reference_manifest = args.reference_manifest.resolve() if args.reference_manifest else None
    references = {}
    if reference_manifest:
        reference_document = json.loads(reference_manifest.read_text(encoding="utf-8"))
        references = {row["case_id"]: row for row in reference_document["references"]}
        for case_id, _, _ in selected:
            reference_id = "tilted_crossing_paths" if case_id in {"resolution_s3", "resolution_s4"} else case_id
            row = references[reference_id]
            path = Path(row["reference"])
            if not path.is_file() or file_hash(path) != row["sha256"]:
                raise ValueError(f"三维参照缺失或摘要不匹配: {case_id}")

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
    warp = PAMO / "simp_cuda/safe_project/warp_"
    warp_commit = subprocess.check_output(
        ["git", "-C", str(warp), "rev-parse", "HEAD"], text=True
    ).strip()
    if warp_commit != WARP_COMMIT:
        raise RuntimeError(f"Warp提交不匹配: {warp_commit}")
    if subprocess.check_output(["git", "-C", str(warp), "status", "--short"], text=True):
        raise RuntimeError("Warp作者工作区必须无修改")

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
        for name in tracked_files(warp):
            source = warp / name
            if source.is_file():
                bundle.add(
                    source,
                    arcname=f"pamo/simp_cuda/safe_project/warp_/{name}",
                    recursive=False,
                )

        for case_id, source, _ in selected:
            target_name = f"{case_id}.obj"
            bundle.add(source, arcname=f"inputs/{target_name}", recursive=False)
            input_row = {
                    "case_id": case_id,
                    "source": str(source),
                    "archive_path": f"inputs/{target_name}",
                    "sha256": file_hash(source),
                }
            if reference_manifest:
                reference_id = "tilted_crossing_paths" if case_id in {"resolution_s3", "resolution_s4"} else case_id
                reference = references[reference_id]
                input_row["reference"] = reference["reference"]
                input_row["reference_sha256"] = reference["sha256"]
                input_row["reference_spacing_mm"] = reference_document["spacing_mm"]
            inputs.append(input_row)

        for path in (HERE / "run_pamo_author.py", HERE / "run_pamo_remote.sh"):
            bundle.add(path, arcname=path.name, recursive=False)

        embedded_manifest = {
            "schema_version": 1,
            "time_beijing": now.strftime("%Y-%m-%d %H:%M:%S"),
            "source_experiment": str(experiment) if experiment else None,
            "source_results_sha256": file_hash(experiment / "results.json") if experiment else None,
            "source_inputs_manifest": str(inputs_manifest) if inputs_manifest else None,
            "source_inputs_manifest_sha256": file_hash(inputs_manifest) if inputs_manifest else None,
            "reference_manifest": str(reference_manifest) if reference_manifest else None,
            "reference_manifest_sha256": file_hash(reference_manifest) if reference_manifest else None,
            "pamo_repository": "https://github.com/SarahWeiii/pamo",
            "pamo_commit": PAMO_COMMIT,
            "pamo_license": "AGPL-3.0",
            "pamo_warp_commit": warp_commit,
            "adapter_sha256": {
                name: file_hash(HERE / name)
                for name in (
                    "prepare_pamo_remote.py", "run_pamo_author.py",
                    "run_pamo_remote.sh", "execute_pamo_remote.py",
                    "audit_pamo_outputs.py",
                )
            },
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
