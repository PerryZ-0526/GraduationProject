"""固定六个已见前缀及同几何用例，检验三角化质量与下一次布尔拒绝的关系。"""

import argparse
import importlib.util
import json
from pathlib import Path
import shlex
import sys

import numpy as np
import paramiko
import trimesh

from audit_followup_candidate import sha256, quality_distribution
from geometry_preservation_audit import mesh_valid
from locality_cleanup import clean_provenance
from locality_masks import save_obj_fp64
from run_constrained_feedback import global_geometry, PROVENANCE
from run_geometry_study import execute, retrieve, save, now


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--assets", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    results = HERE / "实验结果"
    prepared = results / "20261004_完整验证新冻结"
    manifest = read(prepared / "01-完整范围冻结清单.json")
    # 历史失败三例加成功对照三例，不能按新结果筛选或更换。
    selections = [("development_crossing_slab_01", "failure", results / "20261004_统一来源清理六路线反馈"),
                  ("development_long_slab_24", "failure", results / "20261004_约束质量生成完整冻结验证/long"),
                  ("development_long_sphere_24", "failure", results / "20261004_约束质量生成完整冻结验证/long")]
    selections += [("development_" + name, "control", results / "20261004_统一来源清理六路线反馈")
                   for name in ("shallow_slab_01", "vertical_sphere_01", "stop_resume_sphere_01")]
    # 快照隔离近期新增模块，避免另一个工作进程更新源码影响本次诊断。
    snapshot = args.output / "planar_quality.py"
    snapshot.write_bytes((HERE / "planar_quality.py").read_bytes())
    spec = importlib.util.spec_from_file_location("causal_planar_snapshot", snapshot)
    planar = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(planar)
    record = {"time_beijing": now(), "status": "prepared", "selections": [r[:2] for r in selections],
              "planar_snapshot_sha256": sha256(snapshot), "max_planar_flips": 50,
              "registered_csg_budget": 48, "gpu_runs": 0, "rows": [], "stages": [],
              "code_sha256": {name: sha256(HERE / name) for name in
                              ("diagnose_interface_chain.py", "locality_cleanup.py", "locality_retriangulate.py",
                               "geometry_preservation_audit.py")},
              "scope": "已见开发的因果诊断；不是独立路线评价，不修改发布状态；共面数值探针非连续认证"}
    record_path = args.output / "01-因果干预执行账本.json"
    save(record_path, record)
    config = dict(line.split("=", 1) for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines()
                  if line and not line.startswith("#"))
    client = paramiko.SSHClient()
    client.load_host_keys(str(ROOT / ".ssh_known_hosts"))
    client.connect(config["CUDA_SSH_HOST"], port=int(config["CUDA_SSH_PORT"]),
                   username=config["CUDA_SSH_USER"], password=config["CUDA_SSH_PASSWORD"],
                   look_for_keys=False, allow_agent=False, timeout=20)
    del config
    sftp = client.open_sftp()
    remote = "/root/autodl-tmp/graduation_project/causal_" + args.output.name
    if execute(client, ["mkdir", remote])["returncode"]:
        raise RuntimeError("诊断远端目录已经存在，禁止自动重跑")
    record["provenance_binary_sha256"] = execute(client, ["sha256sum", PROVENANCE])["stdout"].split()[0]
    assert record["provenance_binary_sha256"] == "da6a45e3b45b0dceac87629379840046a692cfa3e24da6631234d0d00d50d033"

    def csg(case, treatment, parent_path, tool_path, mode):
        stem = case + "_" + treatment + "_" + mode
        folder = args.output / stem
        folder.mkdir()
        parent_remote, tool_remote = remote + "/" + stem + "_parent.obj", remote + "/" + stem + "_tool.obj"
        for path, target in ((parent_path, parent_remote), (tool_path, tool_remote)):
            sftp.put(str(path), target)
            if execute(client, ["sha256sum", target])["stdout"].split()[0] != sha256(path):
                raise ValueError("远端输入摘要不一致")
        output, labels, log = remote + "/" + stem + ".obj", remote + "/" + stem + ".json", remote + "/" + stem + ".log"
        command = [PROVENANCE, parent_remote, tool_remote, output, labels]
        if mode == "no_simplify":
            command.append("--no-simplify")
        run = execute(client, command, log, timeout=120)
        retrieve(client, sftp, log, folder / "geogram.log")
        row = {"case": case, "treatment": treatment, "mode": mode, "parent_sha256": sha256(parent_path),
               "tool_sha256": sha256(tool_path), "execution": run, "status": "execution_failed"}
        if run["returncode"] == 0:
            retrieve(client, sftp, output, folder / "source.obj")
            retrieve(client, sftp, labels, folder / "labels.json")
            source = trimesh.load(folder / "source.obj", force="mesh", process=False)
            raw_valid, raw_checks = mesh_valid(source)
            # 默认简化标签可能缺失；此占位仅用于同步面索引，不用于声称来源合法。
            row.update(raw_valid=raw_valid, raw_checks=raw_checks, output_sha256=sha256(folder / "source.obj"))
            try:
                cleaned, _, cleanup = clean_provenance(source, np.ones(len(source.faces), dtype=int))
            except ValueError as error:
                row.update(status="cleanup_rejected", cleanup_error=str(error))
            else:
                save_obj_fp64(cleaned, folder / "clean_source.obj")
                valid, checks = mesh_valid(cleaned)
                row.update(status="legal_numeric_output" if valid else "numeric_output_rejected",
                           clean_checks=checks, cleanup=cleanup, quality=quality_distribution(cleaned),
                           clean_sha256=sha256(folder / "clean_source.obj"))
        record["rows"].append(row)
        save(record_path, record)
        print(stem, row["status"], flush=True)

    try:
        record["status"] = "running"
        for rid, group, folder in selections:
            case = args.output / rid
            case.mkdir()
            route = next(r for r in manifest["routes"] if r["id"] == rid)
            parent_path = folder / (rid + "_e0_candidate_boolean") / "candidate.obj"
            source_path = folder / (rid + "_e0_candidate_input") / "clean_source.obj"
            assert parent_path.exists() and source_path.exists()
            old_record = read(folder / "01-反馈执行与独立审计.json")
            published = next(r for r in old_record["rows"] if r["route"] == rid and r["event"] == "e0" and r["branch"] == "candidate")
            assert sha256(parent_path) == published["output_sha256"]
            binary_args = shlex.split(old_record["environment"]["compile"]["command"])
            worker_root = str(Path(binary_args[binary_args.index("-o") + 1]).parent).replace("\\", "/")
            retrieve(client, sftp, worker_root + "/" + rid + "_e0_candidate_boolean/output/before_projection.obj", case / "before_projection.obj")
            parent = trimesh.load(parent_path, force="mesh", process=False)
            counterfactual, intervention = planar.improve_planar(parent, np.ones(len(parent.faces), dtype=int),
                                                                np.ones(len(parent.faces), dtype=bool), max_flips=50)
            save_obj_fp64(counterfactual, case / "counterfactual.obj")
            counterfactual = trimesh.load(case / "counterfactual.obj", force="mesh", process=False)
            valid, checks = mesh_valid(counterfactual)
            distance = global_geometry(counterfactual, parent)
            eligible = valid and intervention["vertices_exact"] and distance["probe_max_mm"] <= 1e-7
            stage = {"route": rid, "group": group, "source_quality": quality_distribution(trimesh.load(source_path, force="mesh", process=False)),
                     "before_projection_quality": quality_distribution(trimesh.load(case / "before_projection.obj", force="mesh", process=False)),
                     "published_parent_quality": quality_distribution(parent), "counterfactual_quality": quality_distribution(counterfactual),
                     "intervention": intervention, "counterfactual_valid": valid, "checks": checks,
                     "geometry_to_original_parent": distance, "eligible": eligible, "parent_sha256": sha256(parent_path)}
            record["stages"].append(stage)
            save(record_path, record)
            tool = next(t for t in route["prefix_tools"] if t["event_id"] == "e1")
            tool_path = prepared / "inputs" / tool["mesh"]
            assert sha256(tool_path) == tool["sha256"]
            for treatment, path in [("original_a", parent_path), ("original_b", parent_path), ("planar_quality", case / "counterfactual.obj")]:
                if treatment == "planar_quality" and not eligible:
                    continue
                for mode in ("no_simplify", "default"):
                    csg(rid, treatment, path, tool_path, mode)
        assets = read(args.assets / "01-同几何因果测试清单.json")
        record["assets_manifest_sha256"] = sha256(args.assets / "01-同几何因果测试清单.json")
        for pair in assets["pairs"]:
            for tool in pair["tools"]:
                tool_path = args.assets / tool["mesh"]
                assert sha256(tool_path) == tool["sha256"]
                for mesh in pair["meshes"]:
                    path = args.assets / mesh["mesh"]
                    assert sha256(path) == mesh["sha256"]
                    csg(pair["id"] + "_" + tool["id"], mesh["id"], path, tool_path, "no_simplify")
        record["status"] = "completed_diagnostic"
        record["finished_beijing"] = now()
        record["source_files_unchanged"] = all(sha256(HERE / name) == expected
                                               for name, expected in record["code_sha256"].items())
        save(record_path, record)
    finally:
        sftp.close()
        client.close()


if __name__ == "__main__":
    main()
