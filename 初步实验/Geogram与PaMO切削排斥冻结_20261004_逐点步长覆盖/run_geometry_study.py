"""自动运行研究一冻结批次，逐帧取回审计并控制父网格反馈。"""

import argparse
from datetime import datetime, timedelta, timezone
import getpass
import json
from pathlib import Path
import shlex
import time

import numpy as np
import paramiko
from scipy.spatial import cKDTree
import trimesh
import pyvista as pv

from audit_followup_candidate import sha256
from audit_pamo_outputs import as_polydata, reference_audit
from geometry_preservation_audit import mesh_valid, preservation, replay_primitives
from run_followup_geogram import contained


HERE = Path(__file__).resolve().parent
REMOTE_BASE = "/root/autodl-tmp/graduation_project"
OLD = REMOTE_BASE + "/followup_20260928_2344"
PYTHON = REMOTE_BASE + "/pamo_quality_20260927_015556_807159_retry3/venv/bin/python"
EXAMPLE = REMOTE_BASE + "/pamo_quality_20260927_015556_807159_retry3/pamo/example.py"
GEO = OLD + "/bin/geogram_boolean"
GEO_LIB = OLD + "/geogram_src/build/followup-linux64-gcc-dynamic/lib"
EXPECTED_EXTENSION = "c0836ff8d36fe5c9e2fca8f27e9a341578aa3d716dfb1d0563784710717353ad"


def now():
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def execute(client, argv, log=None, timeout=120):
    # 非交互SSH不会继承旧会话的动态库路径，显式指定原构建目录。
    if argv[0] == GEO:
        argv = ["env", "LD_LIBRARY_PATH=" + GEO_LIB, *argv]
    command = " ".join(shlex.quote(str(x)) for x in argv)
    if log:
        command = "timeout " + str(timeout) + " " + command + " > " + shlex.quote(log) + " 2>&1"
    started = time.perf_counter()
    _, stdout, stderr = client.exec_command(command, timeout=timeout + 30)
    out, err = stdout.read().decode("utf-8", "replace"), stderr.read().decode("utf-8", "replace")
    rc = stdout.channel.recv_exit_status()
    return {"returncode": rc, "remote_roundtrip_ms": (time.perf_counter() - started) * 1000,
            "stdout": out, "stderr": err, "command": command}


def retrieve(client, sftp, remote, local):
    sftp.get(remote, str(local))
    check = execute(client, ["sha256sum", remote])
    if check["returncode"] or check["stdout"].split()[0] != sha256(local):
        raise ValueError("取回文件摘要不匹配")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--host", default="connect.weste.seetacloud.com")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--split", choices=("development", "evaluation", "application"), required=True)
    args = parser.parse_args()
    prepared, output = args.prepared.resolve(), args.output.resolve()
    if output.exists():
        raise FileExistsError(output)
    manifest_path = prepared / "01-连续几何批次清单.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    routes = [r for r in manifest["routes"] if r["split"] == args.split]
    for route in routes:
        for item in [{"mesh": route["initial_mesh"], "sha256": route["initial_mesh_sha256"]}, *route["prefix_tools"]]:
            if sha256(prepared / "inputs" / item["mesh"]) != item["sha256"]:
                raise ValueError("冻结输入摘要变化")
    output.mkdir(parents=True)
    remote = REMOTE_BASE + "/geometry_study_" + output.name
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    # 凭据仅在无回显终端读取，不写入命令、记录或日志。
    password = getpass.getpass("GPU SSH password: ")
    client.connect(args.host, port=args.port, username="root", password=password,
                   look_for_keys=False, allow_agent=False, timeout=30)
    del password
    sftp = client.open_sftp()
    try:
        setup = execute(client, ["mkdir", remote])
        if setup["returncode"]:
            raise RuntimeError("远端输出目录已存在或无法创建")
        sftp.put(str(prepared / "连续几何输入包.tar.gz"), remote + "/inputs.tar.gz")
        if execute(client, ["tar", "-xzf", remote + "/inputs.tar.gz", "-C", remote])["returncode"]:
            raise RuntimeError("输入包解压失败")
        environment = execute(client, ["env", "-u", "PYTHONPATH", "LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libstdc++.so.6",
            PYTHON, "-c", "import torch,torchcumesh2sdf,hashlib,json; print(json.dumps({'extension_sha256':hashlib.sha256(open(torchcumesh2sdf.__file__,'rb').read()).hexdigest(),'gpu':torch.cuda.get_device_name(0),'torch':torch.__version__}))"])
        if environment["returncode"]:
            raise RuntimeError(environment["stderr"])
        env_info = json.loads(environment["stdout"].strip().splitlines()[-1])
        if env_info["extension_sha256"] != EXPECTED_EXTENSION:
            raise ValueError("实际加载的CUDA符号扩展非冻结原版")
        libraries = execute(client, ["env", "LD_LIBRARY_PATH=" + GEO_LIB, "ldd", GEO])
        if libraries["returncode"] or "not found" in libraries["stdout"]:
            raise RuntimeError("Geogram动态库预检失败")
        env_info["geogram_binary_sha256"] = execute(client, ["sha256sum", GEO])["stdout"].split()[0]
        env_info["geogram_library_sha256"] = execute(client, ["sha256sum", GEO_LIB + "/libgeogram.so"])["stdout"].split()[0]
        ref_root = HERE / "实验结果/20260928_独立解析参照"
        ref_manifest = json.loads((ref_root / "01-参照审计.json").read_text(encoding="utf-8"))
        analytic_refs = {(r["route"], r["event"]): r for r in ref_manifest["rows"]}
        report = {"time_beijing": now(), "manifest_sha256": sha256(manifest_path),
                  "script_sha256": sha256(Path(__file__)), "audit_code_sha256": sha256(HERE / "geometry_preservation_audit.py"),
                  "environment": env_info, "remote": remote, "split": args.split, "rows": [], "status": "running"}
        record = output / "01-连续几何执行与审计.json"
        save(record, report)
        for route in routes:
            rid = route["id"]
            initial = trimesh.load(prepared / "inputs" / route["initial_mesh"], force="mesh", process=False)
            initial_valid, initial_metrics = mesh_valid(initial)
            report.setdefault("initial_audits", {})[rid] = {"valid": initial_valid, "metrics": initial_metrics}
            initial_remote = remote + "/inputs/" + route["initial_mesh"]
            parents = {"C0": initial_remote, "C1": initial_remote}
            previous = {"C0": initial, "C1": initial}
            blocked = {"R": not initial_valid, "C0": not initial_valid, "C1": not initial_valid}
            retained = []
            union = None
            tools = {t["event_id"]: t for t in route["prefix_tools"]}
            for eid in route["cutting_prefix_ids"]:
                primitive = replay_primitives(route, eid)[-1]
                reuse = contained(primitive["start"].tolist(), primitive["end"].tolist(), retained)
                tool_remote = remote + "/inputs/" + tools[eid]["mesh"]
                frame = output / rid / eid
                frame.mkdir(parents=True)
                remote_frame = remote + "/" + rid + "_" + eid
                execute(client, ["mkdir", remote_frame])
                ref_mesh = None
                # 独立累计工具参照与两个反馈分支使用完全相同的离散工具。
                rrow = {"route": rid, "event": eid, "branch": "R", "status": "blocked_by_previous_failure"}
                report["rows"].append(rrow)
                if not blocked["R"]:
                    if union is None:
                        union = tool_remote
                    elif not reuse:
                        target_union = remote_frame + "/union.obj"
                        run = execute(client, [GEO, union, tool_remote, target_union, "--operation", "union"], remote_frame + "/union.log")
                        retrieve(client, sftp, remote_frame + "/union.log", frame / "union.log")
                        rrow["union_run"] = run
                        if run["returncode"]:
                            blocked["R"] = True
                            rrow["status"] = "union_failed"
                        else:
                            union = target_union
                    if not blocked["R"]:
                        rpath = remote_frame + "/R.obj"
                        run = execute(client, [GEO, initial_remote, union, rpath], remote_frame + "/R.log")
                        retrieve(client, sftp, remote_frame + "/R.log", frame / "R.log")
                        rrow["run"] = run
                        if run["returncode"]:
                            blocked["R"] = True
                            rrow["status"] = "geogram_failed"
                        else:
                            retrieve(client, sftp, rpath, frame / "R.obj")
                            raw = trimesh.load(frame / "R.obj", force="mesh", process=False)
                            ref_mesh = trimesh.Trimesh(raw.vertices, raw.faces, process=True, validate=True)
                            valid, m = mesh_valid(ref_mesh)
                            rrow["cleanup_max_vertex_difference_mm"] = float(cKDTree(ref_mesh.vertices).query(raw.vertices)[0].max())
                            valid = valid and rrow["cleanup_max_vertex_difference_mm"] <= 1e-7
                            if route["body"] != "ct":
                                valid = valid and m["components"] == 1 and m["euler_number"] == 2
                            rrow.update(status="reference_valid" if valid else "reference_topology_invalid",
                                        metrics=m, sha256=sha256(frame / "R.obj"))
                            if not valid:
                                blocked["R"], ref_mesh = True, None
                ref = analytic_refs.get((rid, eid))
                analytic = None
                if ref:
                    path = ref_root / ref["mesh"]
                    if sha256(path) != ref["sha256"]:
                        raise ValueError("独立解析参照摘要变化")
                    analytic = pv.read(path)
                for branch in ("C0", "C1"):
                    row = {"route": rid, "event": eid, "branch": branch, "status": "blocked_by_previous_failure"}
                    report["rows"].append(row)
                    if blocked[branch]:
                        continue
                    if reuse:
                        row.update(status="contained_reused", parent_remote=parents[branch],
                                   repeated_geometry_change_mm=0.0, repeated_volume_delta_mm3=0.0)
                        continue
                    geo_remote = remote_frame + "/" + branch + "_geogram.obj"
                    row["parent_remote"] = parents[branch]
                    row["geogram_run"] = execute(client, [GEO, parents[branch], tool_remote, geo_remote],
                                                  remote_frame + "/" + branch + "_geogram.log")
                    retrieve(client, sftp, remote_frame + "/" + branch + "_geogram.log", frame / (branch + "_geogram.log"))
                    if row["geogram_run"]["returncode"]:
                        row["status"], blocked[branch] = "geogram_failed", True
                        continue
                    raw_path = frame / (branch + "_geogram.obj")
                    retrieve(client, sftp, geo_remote, raw_path)
                    raw = trimesh.load(raw_path, force="mesh", process=False)
                    clean = trimesh.Trimesh(raw.vertices, raw.faces, process=True, validate=True)
                    clean_path = frame / (branch + "_clean.obj")
                    clean.export(clean_path, digits=17)
                    clean = trimesh.load(clean_path, force="mesh", process=False)
                    valid, m = mesh_valid(clean)
                    row["input_metrics"] = m
                    row["cleanup_max_vertex_difference_mm"] = float(cKDTree(clean.vertices).query(raw.vertices)[0].max())
                    if not valid or m["fp32_zero_area_faces"] or row["cleanup_max_vertex_difference_mm"] > 1e-7:
                        row["status"], blocked[branch] = "pamo_input_invalid", True
                        continue
                    clean_remote = remote_frame + "/" + branch + "_clean.obj"
                    sftp.put(str(clean_path), clean_remote)
                    p_remote = remote_frame + "/" + branch + "_pamo.obj"
                    row["pamo_run"] = execute(client, ["env", "-u", "PYTHONPATH", "LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libstdc++.so.6",
                        PYTHON, EXAMPLE, "--input", clean_remote, "--output", p_remote, "--ratio", "1.0", "--min-vertex", "0"],
                        remote_frame + "/" + branch + "_pamo.log", timeout=900)
                    retrieve(client, sftp, remote_frame + "/" + branch + "_pamo.log", frame / (branch + "_pamo.log"))
                    if row["pamo_run"]["returncode"]:
                        row["status"], blocked[branch] = "pamo_failed", True
                        continue
                    candidate_path = frame / (branch + "_pamo.obj")
                    retrieve(client, sftp, p_remote, candidate_path)
                    candidate = trimesh.load(candidate_path, force="mesh", process=False)
                    valid, m = mesh_valid(candidate)
                    row.update(output_metrics=m, output_sha256=sha256(candidate_path),
                               preservation=preservation(candidate, initial, route, eid, previous[branch]))
                    geo_ok = False
                    if ref_mesh is not None:
                        row["to_cumulative_reference"] = reference_audit(as_polydata(candidate), as_polydata(ref_mesh))
                        geo_ok = row["to_cumulative_reference"]["sampled_max_mm"] <= .1
                    if analytic is not None:
                        row["to_analytic_discrete_reference"] = reference_audit(as_polydata(candidate), analytic)
                        geo_ok = row["to_analytic_discrete_reference"]["sampled_max_mm"] <= .1 and (geo_ok or ref_mesh is None)
                    expected_topology = (rrow["metrics"]["components"], rrow["metrics"]["euler_number"]) if ref_mesh is not None else (1, 2)
                    topology_matches = (m["components"], m["euler_number"]) == expected_topology
                    row["topology_matches_reference"] = topology_matches
                    accepted = valid and topology_matches and geo_ok and row["preservation"]["quality_all"]["invalid_faces"] == 0
                    row["status"] = "accepted_sampled" if accepted else "output_invalid_or_reference_unavailable"
                    row["continuous_geometry_certificate"] = None
                    if accepted:
                        parents[branch] = clean_remote if branch == "C0" else p_remote
                        previous[branch] = candidate
                    else:
                        blocked[branch] = True
                    print(rid, eid, branch, row["status"], flush=True)
                    save(record, report)
                if not reuse:
                    retained.append((primitive["start"].tolist(), primitive["end"].tolist()))
                save(record, report)
                print("frame_complete", rid, eid, "blocked", blocked, flush=True)
        report["status"], report["finished_beijing"] = "complete_with_recorded_failures", now()
        save(record, report)
    finally:
        sftp.close()
        client.close()


if __name__ == "__main__":
    main()
