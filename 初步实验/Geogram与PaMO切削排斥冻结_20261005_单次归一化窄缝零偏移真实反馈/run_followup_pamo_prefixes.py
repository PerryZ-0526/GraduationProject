"""对已审计的开发前缀运行作者PaMO完整三阶段并逐例记录失败。"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
from time import perf_counter, sleep


EXPECTED_GEOMETRY = {
    "P": "61553a5740ce71e4458ae39678d99a5a6cd586421884795011b83bc7e3af07b1",
    "P_plus_S": "d92c67cde194385025e2b530d5a443e2878bf848402e2ec72101c543f1cacda3",
}
EXPECTED_EXTENSION = {
    "P": "c0836ff8d36fe5c9e2fca8f27e9a341578aa3d716dfb1d0563784710717353ad",
    "P_plus_S": "ddea5be183ddcd740d661f8b675dc6791b75e83abad71d74b2fe279235925f35",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def gpu_used_mib() -> int | None:
    probe = subprocess.run(["nvidia-smi", "--query-gpu=memory.used",
                            "--format=csv,noheader,nounits"],
                           capture_output=True, text=True, timeout=5, check=False)
    if probe.returncode:
        return None
    try:
        return int(probe.stdout.splitlines()[0].strip())
    except (IndexError, ValueError):
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--example", type=Path, required=True)
    parser.add_argument("--geometry-source", type=Path, required=True)
    parser.add_argument("--extension-dir", type=Path, required=True)
    parser.add_argument("--variant", choices=("P", "P_plus_S"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=int, default=900)
    args = parser.parse_args()
    if args.output.exists() and any(args.output.iterdir()):
        raise ValueError("输出目录已有文件，禁止覆盖")
    inputs = args.inputs.resolve()
    manifest_path = inputs / "01-开发合法前缀清单.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if len(manifest["valid"]) != 21 or len(manifest["rejected"]) != 3:
        raise ValueError("合法前缀清单数量不符")
    if sha256(args.geometry_source) != EXPECTED_GEOMETRY[args.variant]:
        raise ValueError("符号分支源码摘要不符")
    env = os.environ.copy()
    env["LD_PRELOAD"] = "/usr/lib/x86_64-linux-gnu/libstdc++.so.6"
    if args.variant == "P_plus_S":
        env["PYTHONPATH"] = str(args.extension_dir.resolve())
    else:
        env.pop("PYTHONPATH", None)
    probe = subprocess.run([str(args.python), "-c",
                            "import json,torch,pamo,torchcumesh2sdf; "
                            "print('MODULE_PATHS='+json.dumps([pamo.__file__,torchcumesh2sdf.__file__]))"],
                           env=env, capture_output=True, text=True, timeout=90, check=False)
    if probe.returncode:
        raise RuntimeError("作者模块或CUDA扩展导入失败")
    tagged = [line.removeprefix("MODULE_PATHS=") for line in probe.stdout.splitlines()
              if line.startswith("MODULE_PATHS=")]
    if len(tagged) != 1:
        raise ValueError("作者模块探针输出不唯一")
    module_paths = [Path(item) for item in json.loads(tagged[0])]
    if len(module_paths) != 2 or sha256(module_paths[1]) != EXPECTED_EXTENSION[args.variant]:
        raise ValueError("实际加载的SDF扩展二进制与声明分支不符")
    args.output.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone(timedelta(hours=8)))
    report = {"schema_version": 1, "time_beijing": now.strftime("%Y-%m-%d %H:%M:%S"),
              "variant": args.variant, "input_manifest_sha256": sha256(manifest_path),
              "example_sha256": sha256(args.example),
              "geometry_source_sha256": sha256(args.geometry_source),
              "loaded_modules": [{"path": str(path), "sha256": sha256(path)}
                                 for path in module_paths],
              "ratio": 1.0, "min_vertex": 0, "full_stages": True,
              "rows": []}
    report_path = args.output / "01-PaMO逐前缀执行记录.json"
    for item in manifest["valid"]:
        path = inputs / item["path"]
        if sha256(path) != item["sha256"]:
            raise ValueError(f"{item['route']}/{item['event']}: 输入摘要不符")
        route_dir = args.output / item["route"]
        route_dir.mkdir(exist_ok=True)
        output = route_dir / f"{item['event']}.obj"
        log = route_dir / f"{item['event']}.log"
        command = [str(args.python), str(args.example), "--input", str(path),
                   "--output", str(output), "--ratio", "1.0", "--min-vertex", "0"]
        started = perf_counter()
        peak_used = None
        with log.open("w", encoding="utf-8") as stream:
            process = subprocess.Popen(command, env=env, stdout=stream, stderr=subprocess.STDOUT)
            while process.poll() is None:
                sample = gpu_used_mib()
                if sample is not None:
                    peak_used = max(peak_used or 0, sample)
                if perf_counter() - started > args.timeout_seconds:
                    process.kill()
                    break
                sleep(0.2)
            returncode = process.wait()
        elapsed_ms = (perf_counter() - started) * 1000
        status = "timeout" if elapsed_ms > args.timeout_seconds * 1000 else (
            "completed" if returncode == 0 and output.is_file() else "failed")
        row = {"route": item["route"], "event": item["event"], "status": status,
               "returncode": returncode, "input_sha256": item["sha256"],
               "output_sha256": sha256(output) if output.is_file() else None,
               "process_wall_ms": elapsed_ms, "sampled_peak_gpu_used_mib": peak_used,
               "log": str(log.relative_to(args.output))}
        report["rows"].append(row)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                               encoding="utf-8")
        print(item["route"], item["event"], status, flush=True)


if __name__ == "__main__":
    main()
