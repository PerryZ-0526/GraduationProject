"""运行冻结薄壁、窄缝与贯通孔输入，审计符号变体的拒绝边界。"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
from time import perf_counter

from run_followup_pamo_prefixes import EXPECTED_EXTENSION, EXPECTED_GEOMETRY


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--example", type=Path, required=True)
    parser.add_argument("--geometry-source", type=Path, required=True)
    parser.add_argument("--extension-dir", type=Path, required=True)
    parser.add_argument("--variant", choices=("P", "P_plus_S"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() and any(args.output.iterdir()):
        raise ValueError("否定性检查输出目录已有文件，禁止覆盖")
    manifest_path = args.inputs / "01-开发输入清单.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    cases = manifest["negative_inputs"]
    if len(cases) != 9 or sha256(args.geometry_source) != EXPECTED_GEOMETRY[args.variant]:
        raise ValueError("否定性输入或符号源码摘要不符")
    env = os.environ.copy()
    env["LD_PRELOAD"] = "/usr/lib/x86_64-linux-gnu/libstdc++.so.6"
    if args.variant == "P_plus_S":
        env["PYTHONPATH"] = str(args.extension_dir.resolve())
    else:
        env.pop("PYTHONPATH", None)
    probe = subprocess.run([str(args.python), "-c",
                            "import json,torch,torchcumesh2sdf; "
                            "print('MODULE_PATH='+json.dumps(torchcumesh2sdf.__file__))"],
                           env=env, capture_output=True, text=True, timeout=90, check=False)
    tagged = [line.removeprefix("MODULE_PATH=") for line in probe.stdout.splitlines()
              if line.startswith("MODULE_PATH=")]
    if probe.returncode or len(tagged) != 1:
        raise RuntimeError("CUDA扩展探针失败")
    module = Path(json.loads(tagged[0]))
    if sha256(module) != EXPECTED_EXTENSION[args.variant]:
        raise ValueError("实际加载的扩展二进制与声明符号分支不符")
    args.output.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone(timedelta(hours=8)))
    report = {"schema_version": 1, "time_beijing": now.strftime("%Y-%m-%d %H:%M:%S"),
              "variant": args.variant, "input_manifest_sha256": sha256(manifest_path),
              "example_sha256": sha256(args.example),
              "geometry_source_sha256": sha256(args.geometry_source),
              "loaded_extension_sha256": sha256(module), "rows": []}
    report_path = args.output / "01-符号否定性执行记录.json"
    for case in cases:
        source = args.inputs / case["mesh"]
        if sha256(source) != case["sha256"]:
            raise ValueError(f"{case['id']}: 输入摘要不符")
        output = args.output / f"{case['id']}.obj"
        log = args.output / f"{case['id']}.log"
        command = [str(args.python), str(args.example), "--input", str(source),
                   "--output", str(output), "--ratio", "1.0", "--min-vertex", "0"]
        started = perf_counter()
        try:
            with log.open("w", encoding="utf-8") as stream:
                completed = subprocess.run(command, env=env, stdout=stream,
                                           stderr=subprocess.STDOUT, timeout=900, check=False)
            status = "completed" if completed.returncode == 0 and output.is_file() else "failed"
            returncode = completed.returncode
        except subprocess.TimeoutExpired:
            status, returncode = "timeout", 124
        row = {"id": case["id"], "expected_components": case["expected_components"],
               "expected_euler_number": case.get("expected_euler_number"),
               "input_sha256": case["sha256"], "status": status,
               "returncode": returncode, "output_sha256": sha256(output) if output.is_file() else None,
               "process_wall_ms": (perf_counter() - started) * 1000,
               "log": log.name}
        report["rows"].append(row)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                               encoding="utf-8")
        print(case["id"], status, flush=True)


if __name__ == "__main__":
    main()
