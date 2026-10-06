"""追加固定父网格的配对重复，排除布尔三角化运行间变动这一混杂因素。"""

import argparse
import json
from pathlib import Path
import random

import numpy as np
import paramiko
import trimesh

from audit_followup_candidate import sha256
from geometry_preservation_audit import mesh_valid
from locality_cleanup import clean_provenance
from locality_masks import save_obj_fp64
from run_constrained_feedback import PROVENANCE
from run_geometry_study import execute, retrieve, save, now


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--diagnostic", type=Path, required=True)
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    results = here / "实验结果"
    original = read(args.diagnostic / "01-因果干预执行账本.json")
    assert original["status"] == "completed_diagnostic"
    manifest = read(results / "20261004_完整验证新冻结/01-完整范围冻结清单.json")
    chosen = ["development_crossing_slab_01", "development_long_slab_24",
              "development_long_sphere_24", "development_stop_resume_sphere_01"]
    jobs = []
    for rid in chosen:
        row = next(r for r in original["rows"] if r["case"] == rid and r["treatment"] == "original_a" and r["mode"] == "no_simplify")
        # 原始父快照直接复用第一次上传的本地来源，不重新生成干预候选。
        root = results / ("20261004_约束质量生成完整冻结验证/long" if "long_" in rid
                          else "20261004_统一来源清理六路线反馈")
        parents = [("original", root / (rid + "_e0_candidate_boolean") / "candidate.obj"),
                   ("planar", args.diagnostic / rid / "counterfactual.obj")]
        assert sha256(parents[0][1]) == row["parent_sha256"]
        route = next(r for r in manifest["routes"] if r["id"] == rid)
        tool = next(t for t in route["prefix_tools"] if t["event_id"] == "e1")
        tool_path = results / "20261004_完整验证新冻结/inputs" / tool["mesh"]
        assert sha256(tool_path) == row["tool_sha256"] == tool["sha256"]
        for repeat in range(8):
            for treatment, path in parents:
                jobs.append({"case": rid, "repeat": repeat, "treatment": treatment,
                             "parent": str(path.resolve()), "parent_sha256": sha256(path),
                             "tool": str(tool_path.resolve()), "tool_sha256": sha256(tool_path)})
    random.Random(20261004).shuffle(jobs)
    record = {"time_beijing": now(), "status": "prepared", "jobs": jobs, "rows": [],
              "selection_reason": "三历史失败及首批出现重放不一致的停钻对照；已见开发诊断，不是预先随机独立样本",
              "registered_additional_csg_budget": 64, "gpu_runs": 0, "source_sha256": sha256(Path(__file__)),
              "endpoint": "同一八位坐标清理后，列明拓扑及退化数值检查是否通过；不是完整临床或连续几何验收"}
    freeze_path = args.diagnostic / "02-同输入配对重放追加冻结.json"
    if freeze_path.exists():
        raise FileExistsError(freeze_path)
    save(freeze_path, record)
    config = dict(line.split("=", 1) for line in (here.parents[1] / ".env").read_text(encoding="utf-8").splitlines()
                  if line and not line.startswith("#"))
    client = paramiko.SSHClient()
    client.load_host_keys(str(here.parents[1] / ".ssh_known_hosts"))
    client.connect(config["CUDA_SSH_HOST"], port=int(config["CUDA_SSH_PORT"]),
                   username=config["CUDA_SSH_USER"], password=config["CUDA_SSH_PASSWORD"],
                   look_for_keys=False, allow_agent=False, timeout=20)
    del config
    sftp = client.open_sftp()
    remote = "/root/autodl-tmp/graduation_project/causal_repeat_" + args.diagnostic.name
    assert execute(client, ["mkdir", remote])["returncode"] == 0
    assert execute(client, ["sha256sum", PROVENANCE])["stdout"].split()[0] == original["provenance_binary_sha256"]
    try:
        record["status"] = "running"
        for index, job in enumerate(jobs):
            folder = args.diagnostic / ("配对重放" + str(index).zfill(2))
            folder.mkdir()
            stem = remote + "/r" + str(index)
            for name in ("parent", "tool"):
                assert sha256(Path(job[name])) == job[name + "_sha256"]
                sftp.put(job[name], stem + "_" + name + ".obj")
                assert execute(client, ["sha256sum", stem + "_" + name + ".obj"])["stdout"].split()[0] == job[name + "_sha256"]
            run = execute(client, [PROVENANCE, stem + "_parent.obj", stem + "_tool.obj", stem + ".obj",
                                   stem + ".json", "--no-simplify"], stem + ".log", timeout=120)
            retrieve(client, sftp, stem + ".log", folder / "geogram.log")
            row = {**job, "execution": run, "status": "execution_failed"}
            if run["returncode"] == 0:
                retrieve(client, sftp, stem + ".obj", folder / "source.obj")
                raw = trimesh.load(folder / "source.obj", force="mesh", process=False)
                row["output_sha256"] = sha256(folder / "source.obj")
                try:
                    cleaned, _, details = clean_provenance(raw, np.ones(len(raw.faces), dtype=int))
                except ValueError as error:
                    row.update(status="cleanup_rejected", error=str(error))
                else:
                    valid, checks = mesh_valid(cleaned)
                    save_obj_fp64(cleaned, folder / "clean_source.obj")
                    row.update(status="legal_numeric_output" if valid else "numeric_output_rejected",
                               checks=checks, cleanup=details, clean_sha256=sha256(folder / "clean_source.obj"))
            record["rows"].append(row)
            save(args.diagnostic / "03-同输入配对重放结果.json", record)
            print(index + 1, "/64", job["case"], job["treatment"], row["status"], flush=True)
        record.update(status="completed_diagnostic", finished_beijing=now())
        save(args.diagnostic / "03-同输入配对重放结果.json", record)
    finally:
        sftp.close()
        client.close()


if __name__ == "__main__":
    main()
