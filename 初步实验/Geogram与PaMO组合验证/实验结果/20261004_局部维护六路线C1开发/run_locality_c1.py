"""六条已见开发路线逐帧局部C1反馈；本机审计后才更新远端父网格。"""

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
from time import perf_counter

import numpy as np
import paramiko
import trimesh

# 复用现有独立审计与共同运动记录，不在新执行器复制评价实现。
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "共同运动记录与方法对照"))
from audit_pamo_outputs import audit_one
from audit_followup_candidate import quality_distribution, vertex_manifold_closed
from locality_diagnostic import far_drift, source_region, verify_labels
from locality_feedback import digest, maintain_frame
from locality_masks import external_contract, make_masks
from motion_record import replay_case
from preflight_geogram_prefixes import metrics
from run_geometry_study import execute, retrieve

ROOT = HERE.parents[1]
RESULTS = HERE / "实验结果"
sys.path.insert(0, str(HERE.parent / "CUDA远程验证"))
from remote import FirstUsePolicy

REMOTE_BASE = "/root/autodl-tmp/graduation_project"
PYTHON = REMOTE_BASE + "/pamo_quality_20260927_015556_807159_retry3/venv/bin/python"
CUDA = REMOTE_BASE + "/locality_cuda_20261004"


def now():
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(output)
    frozen = RESULTS / "20260928_后续输入冻结_v3"
    manifest_path = frozen / "01-冻结清单.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    routes = [r for r in manifest["routes"] if r["split"] == "development"]
    references = json.loads((RESULTS / "20260928_开发解析参照/01-参照审计.json").read_text(encoding="utf-8"))["rows"]
    policy = json.loads((frozen / "02-评价协议.json").read_text(encoding="utf-8"))["replay_policy"]
    provenance = json.loads((RESULTS / "20261004_局部维护来源重放/01-来源重放记录.json").read_text(encoding="utf-8"))
    extension_sha = json.loads((RESULTS / "20261004_局部维护首帧准备/取回输出/pilot_v2/01-GPU执行记录.json").read_text(encoding="utf-8"))["extension_sha256"]
    for route in routes:
        items = [{"mesh": route["initial_mesh"], "sha256": route["initial_mesh_sha256"]}, *route["prefix_tools"]]
        for item in items:
            if digest(frozen / item["mesh"]) != item["sha256"]:
                raise ValueError("冻结输入摘要不符")
    output.mkdir()
    record = output / "01-局部C1逐帧执行与独立审计.json"
    remote = REMOTE_BASE + "/locality_c1_" + datetime.now(timezone(timedelta(hours=8))).strftime("%Y%m%d_%H%M%S")
    names = ("run_locality_c1.py", "locality_feedback.py", "locality_masks.py", "locality_gpu.py", "run_locality_gpu_pilot.py")
    report = {"time_beijing": now(), "scope": "六条已见开发路线，非独立评测或质量匹配效率结论",
              "planned_prefixes": 24, "maximum_maintenance_calls": 72, "collapse_pass_budget": 8,
              "manifest_sha256": digest(manifest_path), "remote": remote,
              "extension_sha256": extension_sha, "geogram_sha256": provenance["binary_sha256"],
              "code_sha256": {name: digest(HERE / name) for name in names}, "rows": [], "status": "running"}
    save(record, report)
    config = dict(line.split("=", 1) for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines()
                  if line and not line.startswith("#"))
    client = paramiko.SSHClient()
    if (ROOT / ".ssh_known_hosts").exists():
        client.load_host_keys(str(ROOT / ".ssh_known_hosts"))
    client.set_missing_host_key_policy(FirstUsePolicy())
    try:
        client.connect(config["CUDA_SSH_HOST"], port=int(config["CUDA_SSH_PORT"]), username=config["CUDA_SSH_USER"],
                       password=config["CUDA_SSH_PASSWORD"], look_for_keys=False, allow_agent=False, timeout=20)
        del config
        with client.open_sftp() as sftp:
            if execute(client, ["mkdir", remote])["returncode"]:
                raise RuntimeError("远端新目录创建失败")
            for name in names:
                (output / name).write_bytes((HERE / name).read_bytes())
                sftp.put(str(output / name), remote + "/" + name)
            geo = provenance["remote"] + "/geogram_provenance"
            for binary, expected in ((geo, provenance["binary_sha256"]), (CUDA + "/build/pamo_locality_cuda.so", extension_sha)):
                check = execute(client, ["sha256sum", binary])
                if check["returncode"] or check["stdout"].split()[0] != expected:
                    raise ValueError("远端实际二进制摘要不符")
            for route in routes:
                parent_path = frozen / route["initial_mesh"]
                state = {"mesh": str(parent_path), "sha256": digest(parent_path), "version": 0}
                blocked = False
                for event in route["cutting_prefix_ids"]:
                    row = {"route": route["id"], "event": event, "status": "blocked_by_previous_failure"}
                    report["rows"].append(row)
                    if blocked:
                        save(record, report)
                        continue
                    started = perf_counter()
                    frame = output / (route["id"] + "_" + event)
                    frame.mkdir()
                    remote_frame = remote + "/" + frame.name
                    execute(client, ["mkdir", remote_frame])
                    tool_info = next(t for t in route["prefix_tools"] if t["event_id"] == event)
                    tool_path = frozen / tool_info["mesh"]
                    sftp.put(state["mesh"], remote_frame + "/parent.obj")
                    sftp.put(str(tool_path), remote_frame + "/tool.obj")
                    row.update(parent_sha256=state["sha256"], parent_version=state["version"], tool_sha256=digest(tool_path))
                    run = execute(client, [geo, remote_frame + "/parent.obj", remote_frame + "/tool.obj",
                                          remote_frame + "/source.obj", remote_frame + "/labels.json", "--no-simplify"],
                                  remote_frame + "/geogram.log", timeout=120)
                    row["geogram_run"] = run
                    retrieve(client, sftp, remote_frame + "/geogram.log", frame / "geogram.log")
                    if run["returncode"]:
                        row["status"], blocked = "geogram_failed", True
                        save(record, report)
                        continue
                    for filename in ("source.obj", "labels.json"):
                        retrieve(client, sftp, remote_frame + "/" + filename, frame / filename)
                    source = trimesh.load(frame / "source.obj", force="mesh", process=False)
                    parent = trimesh.load(state["mesh"], force="mesh", process=False)
                    tool = trimesh.load(tool_path, force="mesh", process=False)
                    bits = json.loads((frame / "labels.json").read_text())["operand_bits"]
                    checks = metrics(source)
                    valid = bool(checks["finite"] and checks["watertight"] and checks["winding_consistent"] and
                                 checks["vertex_manifold_closed"] and checks["zero_area_faces"] == 0 and
                                 checks["fp32_zero_area_faces"] == 0 and checks["self_intersection_faces"] == 0 and
                                 checks["euler_number"] == 2)
                    try:
                        _, _, seam = source_region(source, bits, 0)
                        labels = verify_labels(source, bits, parent, tool, seam)
                        valid = valid and labels["passed_1e_8_mm_numerical_check"]
                        row["source_label_validation"] = labels
                    except ValueError as error:
                        valid = False
                        row["source_label_error"] = str(error)
                    row["input_checks"] = checks
                    ref = next(r for r in references if r["route"] == route["id"] and r["event"] == event)
                    reference = RESULTS / "20260928_开发解析参照" / ref["mesh"]
                    if digest(reference) != ref["sha256"]:
                        raise ValueError("独立离散参照摘要不符")
                    primitives = replay_case(route, policy, event)["primitives"]

                    def build(source_path, method, rings):
                        branch = "full" if method == "full" else "boolean_no_transition" if rings == 0 else "boolean"
                        folder = frame / branch
                        folder.mkdir()
                        remote_output = remote_frame + "/" + branch
                        run = execute(client, ["env", "-u", "PYTHONPATH", "LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libstdc++.so.6",
                            PYTHON, remote + "/run_locality_gpu_pilot.py", "--source", remote_frame + "/source.obj",
                            "--labels", remote_frame + "/labels.json", "--tool", remote_frame + "/tool.obj",
                            "--extension", CUDA, "--output", remote_output, "--methods", branch, "--passes", "8"],
                            remote_frame + "/" + branch + "_launch.log", timeout=950)
                        retrieve(client, sftp, remote_frame + "/" + branch + "_launch.log", folder / "launch.log")
                        if run["returncode"]:
                            raise RuntimeError("CUDA执行失败，返回" + str(run["returncode"]))
                        retrieve(client, sftp, remote_output + "/01-GPU执行记录.json", folder / "01-GPU执行记录.json")
                        execution = json.loads((folder / "01-GPU执行记录.json").read_text())
                        actual = execution["rows"][0]
                        if actual["child_status"] or execution["extension_sha256"] != extension_sha or execution["source_sha256"] != digest(source_path):
                            raise RuntimeError("CUDA子进程失败或输入摘要改变")
                        stem = "r0_" + branch
                        for suffix in (".obj", ".log") + (() if method == "full" else ("_original_ids.npy",)):
                            retrieve(client, sftp, remote_output + "/" + stem + suffix, folder / (stem + suffix))
                        target = folder / (stem + ".obj")
                        if digest(target) != actual["output_sha256"]:
                            raise ValueError("实际候选摘要不符")
                        return target

                    def audit(target, method, rings):
                        candidate = trimesh.load(target, force="mesh", process=False)
                        metrics_audit = audit_one(frame / "source.obj", target, reference)
                        log = target.with_suffix(".log").read_text(encoding="utf-8")
                        evidence = {"topology_passed": bool(metrics_audit["topology_passed"]),
                            "sampled_geometry_passed": bool(metrics_audit["sampled_geometry_passed"]),
                            "vertex_manifold": bool(vertex_manifold_closed(candidate.faces)),
                            "finite_nondegenerate": bool(np.isfinite(candidate.vertices).all() and np.all(candidate.area_faces > 1e-12)),
                            "capacity_unchanged": not ("exceeds max_blocks" in log or "Number of contacts" in log),
                            "metrics": metrics_audit, "quality": quality_distribution(candidate),
                            "far_drift_from_parent": far_drift(parent, candidate, primitives)}
                        if method == "boolean":
                            active, fixed = make_masks(source, bits, tool, "boolean", rings=rings)
                            ids = np.load(target.with_name(target.stem + "_original_ids.npy"))
                            contract = external_contract(source, candidate, ids, active, fixed)
                            evidence.update(fixed_contract_passed=contract["passed"], fixed_contract=contract)
                        return evidence

                    state, control = maintain_frame(state, frame / "source.obj", build, audit, valid)
                    row.update(control=control, status="accepted_sampled" if control["published"] else "retained_parent_and_stopped",
                               published_state=state, full_frame_with_transfer_and_audit_ms=(perf_counter() - started) * 1000)
                    blocked = not control["published"]
                    save(record, report)
                    print(route["id"], event, row["status"], "version", state["version"], flush=True)
            report.update(status="completed_with_recorded_failures", finished_beijing=now())
            save(record, report)
    finally:
        client.close()


if __name__ == "__main__":
    main()
