"""只读重放五个阻断输入的默认布尔，核查来源恢复与数值合法性。"""

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys

import numpy as np
import paramiko
import trimesh

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "共同运动记录与方法对照"))
sys.path.insert(0, str(HERE.parent / "CUDA远程验证"))
from locality_diagnostic import SurfaceQuery, digest
from preflight_geogram_prefixes import metrics
from remote import FirstUsePolicy
from run_geometry_study import execute, retrieve


def main():
    results = HERE / "实验结果"
    batch = results / "20261004_局部维护六路线C1开发_清理与复用"
    previous = json.loads((batch / "01-局部C1逐帧执行与独立审计.json").read_text(encoding="utf-8"))
    provenance = json.loads((results / "20261004_局部维护来源重放/01-来源重放记录.json").read_text(encoding="utf-8"))
    frozen = results / "20260928_后续输入冻结_v3"
    manifest = json.loads((frozen / "01-冻结清单.json").read_text(encoding="utf-8"))
    output = results / "20261004_默认三角化来源恢复诊断"
    if output.exists():
        raise FileExistsError(output)
    output.mkdir()
    record = {"time_beijing": datetime.now(timezone(timedelta(hours=8))).isoformat(),
              "role": "已见阻断父网格只读CPU诊断，无新GPU或发布", "rows": []}
    config = dict(line.split("=", 1) for line in (HERE.parents[1] / ".env").read_text(encoding="utf-8").splitlines()
                  if line and not line.startswith("#"))
    client = paramiko.SSHClient()
    client.load_host_keys(str(HERE.parents[1] / ".ssh_known_hosts"))
    client.set_missing_host_key_policy(FirstUsePolicy())
    try:
        client.connect(config["CUDA_SSH_HOST"], port=int(config["CUDA_SSH_PORT"]), username=config["CUDA_SSH_USER"],
                       password=config["CUDA_SSH_PASSWORD"], look_for_keys=False, allow_agent=False, timeout=20)
        with client.open_sftp() as sftp:
            for row in previous["rows"]:
                if row["status"] != "retained_parent_and_stopped":
                    continue
                name = row["route"] + "_" + row["event"]
                folder = output / name
                folder.mkdir()
                remote = previous["remote"] + "/" + name
                command = [provenance["remote"] + "/geogram_provenance", remote + "/parent.obj", remote + "/tool.obj",
                           remote + "/default_diagnostic.obj", remote + "/default_diagnostic.json"]
                run = execute(client, command, remote + "/default_diagnostic.log")
                for suffix in (".obj", ".json", ".log"):
                    retrieve(client, sftp, remote + "/default_diagnostic" + suffix, folder / ("source" + suffix))
                mesh = trimesh.load(folder / "source.obj", force="mesh", process=False)
                parent = trimesh.load(row["published_state"]["mesh"], force="mesh", process=False)
                route = next(r for r in manifest["routes"] if r["id"] == row["route"])
                tool = trimesh.load(frozen / next(t["mesh"] for t in route["prefix_tools"] if t["event_id"] == row["event"]),
                                    force="mesh", process=False)
                samples = np.concatenate((mesh.triangles, mesh.triangles_center[:, None]), axis=1)
                parent_distance = SurfaceQuery(parent)(samples.reshape(-1, 3))[0].reshape(-1, 4).max(axis=1)
                tool_distance = SurfaceQuery(tool)(samples.reshape(-1, 3))[0].reshape(-1, 4).max(axis=1)
                parent_match, tool_match = parent_distance <= 1e-8, tool_distance <= 1e-8
                inferred = parent_match.astype(int) + 2 * tool_match.astype(int)
                original = np.asarray(json.loads((folder / "source.json").read_text())["operand_bits"])
                missing = original == 0
                recovered = original.copy()
                recovered[missing] = inferred[missing]
                (folder / "recovered_labels.json").write_text(json.dumps({"operand_bits": recovered.tolist(),
                    "scope": "顶点与面心数值几何归类，不是精确来源证书"}, ensure_ascii=False, indent=2), encoding="utf-8")
                result = {"route": row["route"], "event": row["event"], "run": run,
                          "source_sha256": digest(folder / "source.obj"), "metrics": metrics(mesh),
                          "missing_source_faces": int(missing.sum()), "unique_recovered_faces": int((missing & np.isin(inferred, [1, 2])).sum()),
                          "ambiguous_faces": int((missing & (inferred == 3)).sum()), "unmatched_faces": int((missing & (inferred == 0)).sum()),
                          "known_labels_disagree": int(((original == 1) & ~parent_match | (original == 2) & ~tool_match).sum())}
                record["rows"].append(result)
                (output / "01-默认三角化来源恢复诊断.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                print(row["route"], result["metrics"]["zero_area_faces"], result["metrics"]["fp32_zero_area_faces"],
                      result["metrics"]["self_intersection_faces"], result["ambiguous_faces"], result["unmatched_faces"], flush=True)
        record["status"] = "completed"
        (output / "01-默认三角化来源恢复诊断.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    finally:
        client.close()


if __name__ == "__main__":
    main()
