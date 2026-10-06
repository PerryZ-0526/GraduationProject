"""用相同C1输入比较PaMO逐帧独立进程和常驻进程的完整墙钟。"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from time import perf_counter


STEMS = ("crossing_e0", "crossing_e1", "crossing_e2", "crossing_e3",
         "stop_resume_e0", "stop_resume_e1", "stop_resume_e3", "stop_resume_e5")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path: Path, report: dict) -> None:
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_isolated(args: argparse.Namespace, name: str, source: Path, output: Path,
                 log: Path) -> dict:
    env = os.environ.copy()
    env["LD_PRELOAD"] = "/usr/lib/x86_64-linux-gnu/libstdc++.so.6"
    if args.module_path:
        env["PYTHONPATH"] = str(args.module_path.resolve())
    else:
        env.pop("PYTHONPATH", None)
    command = [str(args.python), str(args.example), "--input", str(source),
               "--output", str(output), "--ratio", "1.0", "--min-vertex", "0"]
    started = perf_counter()
    with log.open("w", encoding="utf-8") as stream:
        result = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT,
                                timeout=900, env=env, check=False)
    wall_ms = (perf_counter() - started) * 1000
    content = log.read_text(encoding="utf-8")
    matched = re.search(r"Total time:\s+([0-9.]+)", content)
    return {"case": name, "returncode": result.returncode, "wall_ms": wall_ms,
            "author_internal_ms": float(matched.group(1)) * 1000 if matched else None,
            "output_sha256": sha256(output) if output.is_file() else None}


def run_resident(name: str, source: Path, output: Path, log: Path,
                 clear_cache: bool) -> dict:
    import contextlib
    import gc
    import torch
    import trimesh
    from pamo import PaMO

    started = perf_counter()
    with log.open("w", encoding="utf-8") as stream, contextlib.redirect_stdout(stream):
        before = perf_counter()
        mesh = trimesh.load(source, force="mesh", process=False)
        load_ms = (perf_counter() - before) * 1000
        before = perf_counter()
        model = PaMO(mesh, use_stage1=True, use_stage3=True)
        construct_ms = (perf_counter() - before) * 1000
        before = perf_counter()
        vertices = torch.from_numpy(mesh.vertices).float().cuda()
        faces = torch.from_numpy(mesh.faces).int().cuda()
        torch.cuda.synchronize()
        upload_ms = (perf_counter() - before) * 1000
        before = perf_counter()
        final_vertices, final_faces = model.run(vertices, faces, min_verts=0, ratio=1.0)
        torch.cuda.synchronize()
        run_ms = (perf_counter() - before) * 1000
        before = perf_counter()
        trimesh.Trimesh(vertices=final_vertices, faces=final_faces).export(output)
        export_ms = (perf_counter() - before) * 1000
        del model, mesh, vertices, faces, final_vertices, final_faces
        gc.collect()
        if clear_cache:
            torch.cuda.empty_cache()
    wall_ms = (perf_counter() - started) * 1000
    return {"case": name, "returncode": 0, "wall_ms": wall_ms,
            "load_ms": load_ms, "construct_ms": construct_ms,
            "upload_ms": upload_ms, "run_ms": run_ms,
            "export_ms": export_ms, "output_sha256": sha256(output)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("isolated", "resident", "resident_clear"), required=True)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--example", type=Path, required=True)
    parser.add_argument("--module-path", type=Path)
    parser.add_argument("--rounds", type=int, default=4)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    if args.rounds < 1:
        raise ValueError("轮数至少为1")
    sources = [(name, args.inputs / name / "geogram.obj") for name in STEMS]
    if any(not path.is_file() for _, path in sources):
        raise FileNotFoundError("C1输入未齐全")
    args.output.mkdir(parents=True)
    report = {"schema_version": 1,
              "time_beijing": datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S"),
              "mode": args.mode, "rounds": args.rounds,
              "clear_torch_cache_between_frames": args.mode == "resident_clear",
              "module_path": str(args.module_path) if args.module_path else None,
              "module_sha256": sha256(args.module_path / "pamo" / "__init__.py")
              if args.module_path else None,
              "example_sha256": sha256(args.example),
              "input_sha256": {name: sha256(path) for name, path in sources},
              "rows": []}
    report_path = args.output / "report.json"
    save(report_path, report)
    for round_index in range(args.rounds):
        for name, source in sources:
            stem = f"r{round_index}_{name}"
            output = args.output / f"{stem}.obj"
            log = args.output / f"{stem}.log"
            try:
                row = (run_isolated(args, name, source, output, log)
                       if args.mode == "isolated" else run_resident(
                           name, source, output, log, args.mode == "resident_clear"))
            except Exception as error:
                row = {"case": name, "returncode": None, "error": str(error)}
            row["round"] = round_index
            report["rows"].append(row)
            save(report_path, report)
            print(round_index, name, row.get("wall_ms"), row.get("error", ""), flush=True)
            if row.get("returncode") != 0:
                raise RuntimeError(f"{stem}失败，已停止该分支")


if __name__ == "__main__":
    main()
