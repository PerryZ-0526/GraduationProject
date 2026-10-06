"""在授权实例重放八张已见C1布尔输入，验证面来源属性与几何输出。"""

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import shlex
import sys
from time import perf_counter

import paramiko

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE.parent / "CUDA远程验证"))
from remote import FirstUsePolicy


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    if out.exists():
        raise FileExistsError(out)
    out.mkdir(parents=True)
    config = dict(line.split("=", 1) for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines()
                  if line and not line.startswith("#"))
    client = paramiko.SSHClient()
    if (ROOT / ".ssh_known_hosts").exists():
        client.load_host_keys(str(ROOT / ".ssh_known_hosts"))
    client.set_missing_host_key_policy(FirstUsePolicy())
    prepared = HERE / "实验结果/20260929_C1试运行准备"
    frozen = HERE / "实验结果/20260928_后续输入冻结_v3"
    manifest = json.loads((prepared / "01-C1试运行清单.json").read_text(encoding="utf-8"))
    remote = "/root/autodl-tmp/graduation_project/locality_" + datetime.now(timezone(timedelta(hours=8))).strftime("%Y%m%d_%H%M%S")
    report = {"time_beijing": datetime.now(timezone(timedelta(hours=8))).isoformat(),
              "remote": remote, "purpose": "seen_C1_provenance_diagnostic_no_new_test_access",
              "adapter_sha256": digest(HERE / "geogram_provenance.cpp"), "rows": []}

    def save():
        (out / "01-来源重放记录.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def execute(command, log):
        start = perf_counter()
        _, stdout, _ = client.exec_command(command, timeout=180)
        stdout.channel.set_combine_stderr(True)
        text = stdout.read().decode("utf-8", errors="replace")
        rc = stdout.channel.recv_exit_status()
        log.write_text(text, encoding="utf-8")
        return rc, (perf_counter() - start) * 1000

    try:
        client.connect(config["CUDA_SSH_HOST"], port=int(config["CUDA_SSH_PORT"]), username=config["CUDA_SSH_USER"],
                       password=config["CUDA_SSH_PASSWORD"], look_for_keys=False, allow_agent=False,
                       timeout=20, auth_timeout=20)
        client.exec_command("mkdir -p " + shlex.quote(remote))[1].channel.recv_exit_status()
        with client.open_sftp() as sftp:
            sftp.put(str(HERE / "geogram_provenance.cpp"), remote + "/adapter.cpp")
            source = "/root/autodl-tmp/graduation_project/followup_20260928_2344/geogram_src"
            lib = source + "/build/followup-linux64-gcc-dynamic/lib"
            command = " ".join(["g++ -O3 -std=c++17", shlex.quote(remote + "/adapter.cpp"),
                                "-I" + shlex.quote(source + "/src/lib"), "-L" + shlex.quote(lib),
                                "-Wl,-rpath," + shlex.quote(lib), "-lgeogram -o", shlex.quote(remote + "/geogram_provenance")])
            rc, ms = execute(command, out / "build.log")
            report["build"] = {"returncode": rc, "wall_ms": ms}
            save()
            if rc:
                raise RuntimeError("来源适配器编译失败，见build.log")
            sftp.get(remote + "/geogram_provenance", str(out / "geogram_provenance"))
            report["binary_sha256"] = digest(out / "geogram_provenance")
            for route in manifest["routes"]:
                kind = "crossing" if route["category"] == "crossing" else "stop_resume"
                parent = frozen / route["initial_mesh"]
                for event in route["cutting_prefix_ids"]:
                    case = kind + "_" + event
                    original = prepared / "取回输出" / case
                    step = json.loads((original / "step.json").read_text(encoding="utf-8"))
                    tool = next(t for t in route["prefix_tools"] if t["event_id"] == event)
                    if digest(parent) != step["parent_sha256"] or digest(frozen / tool["mesh"]) != step["tool_sha256"]:
                        raise ValueError("历史父状态或工具摘要不匹配: " + case)
                    folder = out / case
                    folder.mkdir()
                    sftp.put(str(parent), remote + "/parent.obj")
                    sftp.put(str(frozen / tool["mesh"]), remote + "/tool.obj")
                    for mode in ("default", "no_simplify"):
                        command = " ".join(map(shlex.quote, [remote + "/geogram_provenance", remote + "/parent.obj",
                                                            remote + "/tool.obj", remote + "/result.obj", remote + "/labels.json"]))
                        if mode == "no_simplify":
                            command += " --no-simplify"
                        rc, ms = execute(command, folder / (mode + ".log"))
                        row = {"case": case, "route": route["id"], "event": event, "mode": mode,
                               "parent_sha256": digest(parent), "tool_sha256": tool["sha256"],
                               "historical_geogram_sha256": digest(original / "geogram.obj"),
                               "returncode": rc, "ssh_command_wall_ms": ms}
                        if rc == 0:
                            sftp.get(remote + "/result.obj", str(folder / (mode + ".obj")))
                            sftp.get(remote + "/labels.json", str(folder / (mode + ".json")))
                            row["output_sha256"] = digest(folder / (mode + ".obj"))
                            row["labels_sha256"] = digest(folder / (mode + ".json"))
                            row["byte_equal_historical"] = row["output_sha256"] == row["historical_geogram_sha256"]
                            bits = json.loads((folder / (mode + ".json")).read_text())["operand_bits"]
                            row["operand_counts"] = {str(b): bits.count(b) for b in sorted(set(bits))}
                        report["rows"].append(row)
                        save()
                        print(case, mode, rc, row.get("operand_counts"), flush=True)
                    parent = original / "pamo.obj"
            report["status"] = "completed"
            save()
    finally:
        client.close()


if __name__ == "__main__":
    main()
