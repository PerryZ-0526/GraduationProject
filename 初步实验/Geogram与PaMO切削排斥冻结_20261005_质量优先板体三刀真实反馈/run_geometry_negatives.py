"""在同一原版PaMO上复核冻结薄壁、窄缝和贯通孔，保留损失证据。"""

import argparse
import getpass
import json
from pathlib import Path

import paramiko
import trimesh

from run_geometry_study import EXAMPLE, PYTHON, REMOTE_BASE, EXPECTED_EXTENSION, execute, now, retrieve, save
from geometry_preservation_audit import mesh_valid
from audit_pamo_outputs import as_polydata, reference_audit
from audit_followup_candidate import quality_distribution, sha256


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    args.output.mkdir(parents=True)
    manifest_path = args.prepared / "01-连续几何批次清单.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    remote = REMOTE_BASE + "/geometry_negative_" + args.output.name
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    password = getpass.getpass("GPU SSH password: ")
    client.connect("connect.weste.seetacloud.com", port=args.port, username="root", password=password,
                   look_for_keys=False, allow_agent=False, timeout=30)
    del password
    sftp = client.open_sftp()
    try:
        if execute(client, ["mkdir", remote])["returncode"]:
            raise RuntimeError("远端输出目录已存在或无法创建")
        # 每批重新核对实际加载的CUDA扩展，避免沿用另一会话的环境判断。
        environment = execute(client, ["env", "-u", "PYTHONPATH", "LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libstdc++.so.6",
            PYTHON, "-c", "import torch,torchcumesh2sdf,hashlib,json; print(json.dumps({'extension_sha256':hashlib.sha256(open(torchcumesh2sdf.__file__,'rb').read()).hexdigest(),'gpu':torch.cuda.get_device_name(0)}))"])
        if environment["returncode"]:
            raise RuntimeError(environment["stderr"])
        env_info = json.loads(environment["stdout"].strip().splitlines()[-1])
        if env_info["extension_sha256"] != EXPECTED_EXTENSION:
            raise ValueError("实际加载的CUDA符号扩展非冻结原版")
        report = {"time_beijing": now(), "manifest_sha256": sha256(manifest_path),
                  "environment": env_info, "script_sha256": sha256(Path(__file__)), "rows": []}
        for item in manifest["negative_inputs"]:
            source = args.prepared / "inputs" / item["mesh"]
            if sha256(source) != item["sha256"]:
                raise ValueError("否定性输入摘要变化")
            path = args.output / item["id"]
            path.mkdir()
            source_remote = remote + "/" + item["mesh"]
            target_remote = remote + "/" + item["id"] + "_pamo.obj"
            log_remote = remote + "/" + item["id"] + ".log"
            sftp.put(str(source), source_remote)
            row = {"id": item["id"], "feature_width_mm": item["feature_width_mm"]}
            report["rows"].append(row)
            row["run"] = execute(client, ["env", "-u", "PYTHONPATH", "LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libstdc++.so.6",
                PYTHON, EXAMPLE, "--input", source_remote, "--output", target_remote,
                "--ratio", "1.0", "--min-vertex", "0"], log_remote, timeout=900)
            retrieve(client, sftp, log_remote, path / "pamo.log")
            if row["run"]["returncode"]:
                row["status"] = "execution_failed"
            else:
                retrieve(client, sftp, target_remote, path / "pamo.obj")
                original = trimesh.load(source, force="mesh", process=False)
                result = trimesh.load(path / "pamo.obj", force="mesh", process=False)
                valid, m = mesh_valid(result)
                _, before = mesh_valid(original)
                row.update(input_metrics=before, output_metrics=m, output_sha256=sha256(path / "pamo.obj"),
                           sampled_geometry=reference_audit(as_polydata(result), as_polydata(original)),
                           quality=quality_distribution(result))
                topology = (m["components"], m["euler_number"]) == (before["components"], before["euler_number"])
                row["status"] = "preserved_sampled" if valid and topology and row["sampled_geometry"]["sampled_max_mm"] <= .1 else "not_preserved"
            save(args.output / "01-薄壁窄缝孔洞审计.json", report)
            print(item["id"], row["status"], flush=True)
    finally:
        sftp.close()
        client.close()


if __name__ == "__main__":
    main()
