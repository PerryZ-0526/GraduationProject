"""固定目标边长后比较边界约束，再在相同解除策略下比较尺度；仅做CPU诊断。"""

import argparse
import json
from pathlib import Path
import random
import shlex

import numpy as np
import paramiko
import trimesh

from audit_followup_candidate import sha256, quality_distribution
from geometry_preservation_audit import mesh_valid
from locality_masks import make_masks, save_obj_fp64
from run_constrained_feedback import global_geometry
from run_geometry_study import execute, retrieve, save, now


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--diagnostic", type=Path, required=True)
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    results = here / "实验结果"
    diagnostic = read(args.diagnostic / "01-因果干预执行账本.json")
    manifest = read(results / "20261004_完整验证新冻结/01-完整范围冻结清单.json")
    jobs = []
    sources = {}
    for stage in diagnostic["stages"]:
        rid = stage["route"]
        root = results / ("20261004_约束质量生成完整冻结验证/long" if "long_" in rid else "20261004_统一来源清理六路线反馈")
        source_path = root / (rid + "_e0_candidate_input") / "clean_source.obj"
        source = trimesh.load(source_path, force="mesh", process=False)
        bits = np.asarray(read(source_path.parent / "clean_labels.json")["operand_bits"])
        route = next(r for r in manifest["routes"] if r["id"] == rid)
        tool = next(t for t in route["prefix_tools"] if t["event_id"] == "e0")
        tool_path = results / "20261004_完整验证新冻结/inputs" / tool["mesh"]
        assert sha256(tool_path) == tool["sha256"]
        active, fixed = make_masks(source, bits, trimesh.load(tool_path, force="mesh", process=False), "boolean", 2)
        details = read(root / (rid + "_e0_candidate_boolean") / "details.json")
        old = read(root / "01-反馈执行与独立审计.json")
        command = shlex.split(old["environment"]["compile"]["command"])
        binary = command[command.index("-o") + 1]
        sources[rid] = (source_path, source, bits, active, fixed, binary, old["environment"]["executable_sha256"])
        for repeat in range(2):
            for policy in ("fixed_high", "released_high", "released_low"):
                jobs.append({"route": rid, "policy": policy, "repeat": repeat,
                             "requested_mm": details["requested_edge_length_mm"] if policy.endswith("low")
                             else details["actual_edge_length_mm"], "common_high_mm": details["actual_edge_length_mm"],
                             "source_sha256": sha256(source_path), "labels_sha256": sha256(source_path.parent / "clean_labels.json")})
    random.Random(20261004).shuffle(jobs)
    record = {"time_beijing": now(), "status": "prepared", "jobs": jobs, "rows": [],
              "source_sha256": sha256(Path(__file__)), "registered_cpu_remesh_budget": 36, "gpu_runs": 0,
              "scope": "六个已见输入；同高尺度固定/解除边界及解除后低尺度，三次CGAL迭代；不发布、不把投影前结果当作完整PaMO候选"}
    freeze = args.diagnostic / "06-等尺度边界干预冻结.json"
    if freeze.exists():
        raise FileExistsError(freeze)
    save(freeze, record)
    config = dict(line.split("=", 1) for line in (here.parents[1] / ".env").read_text(encoding="utf-8").splitlines()
                  if line and not line.startswith("#"))
    client = paramiko.SSHClient()
    client.load_host_keys(str(here.parents[1] / ".ssh_known_hosts"))
    client.connect(config["CUDA_SSH_HOST"], port=int(config["CUDA_SSH_PORT"]), username=config["CUDA_SSH_USER"],
                   password=config["CUDA_SSH_PASSWORD"], look_for_keys=False, allow_agent=False, timeout=20)
    del config
    sftp = client.open_sftp()
    remote = "/root/autodl-tmp/graduation_project/causal_factorial_" + args.diagnostic.name
    assert execute(client, ["mkdir", remote])["returncode"] == 0
    try:
        for rid, (path, source, bits, active, fixed, binary, expected) in sources.items():
            assert execute(client, ["sha256sum", binary])["stdout"].split()[0] == expected
            sftp.put(str(path), remote + "/" + rid + ".obj")
            assert execute(client, ["sha256sum", remote + "/" + rid + ".obj"])["stdout"].split()[0] == sha256(path)
        record["status"] = "running"
        for index, job in enumerate(jobs):
            rid = job["route"]
            path, source, bits, active, fixed, binary, expected = sources[rid]
            assert sha256(path) == job["source_sha256"]
            folder = args.diagnostic / ("等尺度干预" + str(index).zfill(2))
            folder.mkdir()
            protected = job["policy"] == "fixed_high"
            selected_fixed = fixed.copy()
            if not protected:
                selected_fixed[np.unique(source.faces[active])] = False
            mask = folder / "mask.txt"
            with mask.open("w", encoding="utf-8") as stream:
                stream.write(f"{len(source.vertices)} {len(source.faces)} {int(protected)}\n")
                stream.writelines(f"{int(value)}\n" for value in selected_fixed)
                stream.writelines(f"{int(a)} {int(b)}\n" for a, b in zip(active, bits))
            stem = remote + "/r" + str(index)
            sftp.put(str(mask), stem + "_mask.txt")
            run = execute(client, [binary, remote + "/" + rid + ".obj", stem + "_mask.txt", stem + ".obj",
                                   str(job["requested_mm"]), stem + "_mapping.txt"], stem + ".log", timeout=120)
            retrieve(client, sftp, stem + ".log", folder / "remesh.log")
            row = {**job, "execution": run, "status": "execution_failed"}
            if run["returncode"] == 0:
                retrieve(client, sftp, stem + ".obj", folder / "raw_remeshed.obj")
                retrieve(client, sftp, stem + "_mapping.txt", folder / "mapping.txt")
                lines = (folder / "mapping.txt").read_text().splitlines()
                actual, maximum = map(float, lines[0].split())
                mapping = np.asarray([list(map(int, line.split())) for line in lines[1:]])
                candidate = trimesh.load(folder / "raw_remeshed.obj", force="mesh", process=False)
                assert mapping.shape == (len(candidate.vertices), 2)
                restore = (mapping[:, 0] >= 0) & (mapping[:, 1] != 0)
                candidate.vertices[restore] = source.vertices[mapping[restore, 0]]
                save_obj_fp64(candidate, folder / "restored_remeshed.obj")
                valid, checks = mesh_valid(candidate)
                if job["policy"].endswith("high"):
                    assert abs(actual - job["common_high_mm"]) <= 1e-12
                row.update(status="remeshed_numeric_valid" if valid else "remeshed_numeric_rejected", actual_mm=actual,
                           maximum_protected_edge_mm=maximum, quality=quality_distribution(candidate), checks=checks,
                           to_source=global_geometry(candidate, source), output_sha256=sha256(folder / "restored_remeshed.obj"))
            record["rows"].append(row)
            save(args.diagnostic / "07-等尺度边界与尺度分离结果.json", record)
            print(index + 1, "/36", rid, job["policy"], row["status"], flush=True)
        record.update(status="completed_diagnostic", finished_beijing=now())
        save(args.diagnostic / "07-等尺度边界与尺度分离结果.json", record)
    finally:
        sftp.close()
        client.close()


if __name__ == "__main__":
    main()
