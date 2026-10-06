"""同机交错配对局部质量生成，逐输出取回并独立审计。"""

import argparse
import getpass
import hashlib
import json
import os
from pathlib import Path
import random
from time import perf_counter

import paramiko
import trimesh

from audit_followup_candidate import sha256, quality_distribution
from audit_pamo_outputs import as_polydata, reference_audit
from constrained_quality import fixed_surface_contract
from geometry_preservation_audit import mesh_valid
from locality_masks import make_masks
from run_geometry_study import execute, retrieve, save, now, PYTHON, REMOTE_BASE, EXPECTED_EXTENSION

HERE = Path(__file__).resolve().parent


class RemoteQuality:
    """两个实验入口共用隔离编译与取回协议，不改作者环境或二进制。"""
    def __init__(self, output, port):
        self.output = Path(output)
        # 加入完整本机路径摘要，避免不同批次的同名阶段覆盖远端证据。
        identity = hashlib.sha256(str(self.output.resolve()).encode("utf-8")).hexdigest()[:12]
        self.remote = REMOTE_BASE + "/constrained_" + self.output.name + "_" + identity
        self.client = paramiko.SSHClient()
        self.client.load_system_host_keys()
        password = getpass.getpass("GPU SSH password: ")
        # 用户更换实例区域时显式指定连接主机，默认保留历史端点。
        host = os.environ.get("GPU_SSH_HOST", "connect.weste.seetacloud.com")
        self.client.connect(host, port=port, username="root", password=password,
                            look_for_keys=False, allow_agent=False, timeout=30)
        del password
        self.client.get_transport().set_keepalive(30)
        self.sftp = self.client.open_sftp()

    def setup(self):
        if execute(self.client, ["mkdir", self.remote])["returncode"]:
            raise RuntimeError("远端目录已存在或不可创建")
        files = ("constrained_remesh.cpp", "constrained_quality.py", "run_constrained_worker.py",
                 "locality_masks.py", "locality_gpu.py")
        for name in files:
            self.sftp.put(str(HERE / name), self.remote + "/" + name)
        compile_log = self.remote + "/compile.log"
        result = execute(self.client, ["g++", "-O1", "-std=c++17", self.remote + "/constrained_remesh.cpp",
            "-lgmp", "-lmpfr", "-o", self.remote + "/constrained_remesh"], compile_log, timeout=300)
        retrieve(self.client, self.sftp, compile_log, self.output / "compile.log")
        if result["returncode"]:
            raise RuntimeError("CGAL编译失败，见compile.log")
        # 核对实际作者扩展和设备，防止另一个会话的PYTHONPATH改变基线。
        environment = execute(self.client, ["env", "LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libstdc++.so.6",
            "PYTHONPATH=" + self.remote, PYTHON, "-c",
            "import torch,torchcumesh2sdf,hashlib,json; print(json.dumps({'gpu':torch.cuda.get_device_name(0),'torch':torch.__version__,'extension_sha256':hashlib.sha256(open(torchcumesh2sdf.__file__,'rb').read()).hexdigest()}))"])
        if environment["returncode"]:
            raise RuntimeError(environment["stderr"])
        info = json.loads(environment["stdout"].strip().splitlines()[-1])
        if info["extension_sha256"] != EXPECTED_EXTENSION:
            raise ValueError("原版CUDA符号扩展摘要改变")
        return {"code_sha256": {name: sha256(HERE / name) for name in files}, "compile": result, "device": info,
            "executable_sha256": execute(self.client, ["sha256sum", self.remote + "/constrained_remesh"])["stdout"].split()[0],
            "dependency": execute(self.client, ["dpkg-query", "-W", "libcgal-dev"])["stdout"].strip()}

    def run(self, source, labels, tool, method, folder):
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=True)
        remote = self.remote + "/" + folder.name
        exists = execute(self.client, ["test", "-d", remote])["returncode"] == 0
        if exists:
            # 连接恢复先检查同一任务的进程与产物，不能因观察中断重跑已完成CUDA任务。
            running = execute(self.client, ["pgrep", "-af", "run_constrained_worker.py"])
            lines = [line for line in running["stdout"].splitlines() if remote + "/source.obj" in line]
            if lines:
                raise RuntimeError("原候选进程仍在运行，先等待其PID：" + lines[0])
            try:
                self.sftp.stat(remote + "/output/details.json")
            except FileNotFoundError:
                log_path = remote + "/worker.log"
                self.sftp.stat(log_path)
                retrieve(self.client, self.sftp, log_path, folder / "worker.log")
                return {"method": method, "status": "execution_failed", "recovered_after_disconnect": True,
                        "execution": {"returncode": "terminal_without_success_record", "remote_roundtrip_ms": None}}
            for name in ("candidate.obj", "details.json"):
                retrieve(self.client, self.sftp, remote + "/output/" + name, folder / name)
            retrieve(self.client, self.sftp, remote + "/worker.log", folder / "worker.log")
            return {"method": method, "execution": {"returncode": 0, "remote_roundtrip_ms": None},
                    "recovered_after_disconnect": True, "output_sha256": sha256(folder / "candidate.obj"),
                    **json.loads((folder / "details.json").read_text(encoding="utf-8"))}
        if execute(self.client, ["mkdir", remote])["returncode"]:
            raise RuntimeError("候选远端目录无法创建")
        inputs_sha = {}
        for path, name in ((source, "source.obj"), (labels, "labels.json"), (tool, "tool.obj")):
            self.sftp.put(str(path), remote + "/" + name)
            inputs_sha[name] = sha256(path)
            if execute(self.client, ["sha256sum", remote + "/" + name])["stdout"].split()[0] != inputs_sha[name]:
                raise ValueError("远端实际输入摘要不匹配")
        command = ["env", "LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libstdc++.so.6", "PYTHONPATH=" + self.remote,
            PYTHON, self.remote + "/run_constrained_worker.py", "--source", remote + "/source.obj",
            "--labels", remote + "/labels.json", "--tool", remote + "/tool.obj",
            "--executable", self.remote + "/constrained_remesh", "--method", method, "--output", remote + "/output"]
        result = execute(self.client, command, remote + "/worker.log", timeout=900)
        retrieve(self.client, self.sftp, remote + "/worker.log", folder / "worker.log")
        row = {"execution": result, "method": method, "status": "execution_failed", "inputs_sha256": inputs_sha}
        if result["returncode"] == 0:
            for name in ("candidate.obj", "details.json"):
                retrieve(self.client, self.sftp, remote + "/output/" + name, folder / name)
            row.update(json.loads((folder / "details.json").read_text(encoding="utf-8")))
            row["output_sha256"] = sha256(folder / "candidate.obj")
        return row

    def close(self):
        self.sftp.close()
        self.client.close()


def audit_candidate(source_path, tool_path, labels_path, folder, row):
    if row["execution"]["returncode"]:
        return row
    started = perf_counter()
    source = trimesh.load(source_path, force="mesh", process=False)
    candidate = trimesh.load(Path(folder) / "candidate.obj", force="mesh", process=False)
    valid, metrics = mesh_valid(candidate)
    distance = reference_audit(as_polydata(candidate), as_polydata(source))
    bits = json.loads(Path(labels_path).read_text())["operand_bits"]
    contract = None
    if row["method"] != "full":
        tool = trimesh.load(tool_path, force="mesh", process=False)
        mode = row["method"] if row["method"] in ("global", "spatial") else "boolean"
        rings = 0 if row["method"] == "no_transition" else 4 if row["method"] == "expanded" else 2
        active, fixed = make_masks(source, bits, tool, mode, rings)
        contract = fixed_surface_contract(source, candidate, active, fixed)
    log = (Path(folder) / "worker.log").read_text(encoding="utf-8")
    capacity_changed = "exceeds max_blocks" in log or "Number of contacts" in log
    _, source_metrics = mesh_valid(source)
    same_topology = (metrics["components"], metrics["euler_number"]) == (
        source_metrics["components"], int(source.euler_number))
    # 几何偏差保留统计，不以0.1毫米作为输出拒绝条件。
    row.update(output_metrics=metrics, to_geogram_input=distance, quality=quality_distribution(candidate),
        source_quality=quality_distribution(source), fixed_contract=contract, capacity_changed=capacity_changed,
        audited_source_sha256=sha256(source_path), status="accepted_sampled" if valid and same_topology
            and not capacity_changed
            and (contract is None or contract["passed"] or row["method"] == "no_boundary") else "audit_rejected")
    row["geometry_policy"] = "report_only_no_distance_stop"
    row["independent_audit_ms"] = (perf_counter() - started) * 1000
    row["continuous_geometry_certified"] = False
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--rounds", type=int, default=1)
    parser.add_argument("--case-limit", type=int, default=8)
    parser.add_argument("--methods", nargs="+", default=["full", "global", "spatial", "boolean", "no_transition", "no_boundary", "no_projection"])
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    if args.output.exists() and not args.resume:
        raise FileExistsError(args.output)
    args.output.mkdir(parents=True, exist_ok=args.resume)
    manifest = json.loads((args.prepared / "01-保存帧开发批次.json").read_text(encoding="utf-8"))
    report = {"time_beijing": now(), "role": "seen_development_saved_inputs_not_feedback", "rows": [], "status": "running"}
    if args.resume:
        report = json.loads((args.output / "01-质量生成配对与审计.json").read_text(encoding="utf-8"))
        report["resumed_beijing"] = now()
    engine = RemoteQuality(args.output, args.port)
    try:
        if args.resume:
            for name, expected in report["environment"]["code_sha256"].items():
                actual = execute(engine.client, ["sha256sum", engine.remote + "/" + name])["stdout"].split()[0]
                if actual != expected:
                    raise ValueError("原批次远端源码变化，不允许混入新方法")
        else:
            report["environment"] = engine.setup()
        completed = {(r["case"], r["round"], r["method"]) for r in report["rows"]}
        randomizer = random.Random(20261004)
        for case in manifest["cases"][:args.case_limit]:
            inputs = args.prepared / case["case"]
            valid, metrics = mesh_valid(trimesh.load(inputs / "source.obj", force="mesh", process=False))
            for n in range(args.rounds):
                order = list(args.methods)
                randomizer.shuffle(order)
                for method in order:
                    if (case["case"], n, method) in completed:
                        continue
                    folder = args.output / (case["case"] + f"_r{n}_" + method)
                    if not valid or metrics["fp32_zero_area_faces"]:
                        row = {"method": method, "status": "input_rejected", "input_metrics": metrics}
                    else:
                        row = engine.run(inputs / "source.obj", inputs / "labels.json", inputs / "tool.obj", method, folder)
                        row = audit_candidate(inputs / "source.obj", inputs / "tool.obj", inputs / "labels.json", folder, row)
                    row.update(case=case["case"], round=n)
                    report["rows"].append(row)
                    save(args.output / "01-质量生成配对与审计.json", report)
                    print(case["case"], n, method, row["status"], flush=True)
        report["status"] = "completed_with_recorded_failures"
        save(args.output / "01-质量生成配对与审计.json", report)
    finally:
        engine.close()


if __name__ == "__main__":
    main()
