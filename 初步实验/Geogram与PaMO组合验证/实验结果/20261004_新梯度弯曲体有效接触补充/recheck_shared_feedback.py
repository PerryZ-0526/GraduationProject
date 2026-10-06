"""重加载公开开发输出，复核实际父链、保存摘要、输入几何与累计参照。"""
import argparse
import json
import shlex
from pathlib import Path
import numpy as np
import trimesh
from audit_followup_candidate import sha256
from exact_alarm_contact import mesh_valid_exact_contacts
from run_constrained_feedback import global_geometry
from run_geometry_study import now, retrieve
from run_constrained_batch import RemoteQuality


def recheck(prepared, output, remote=None):
    manifest = json.loads((prepared / "01-完整范围冻结清单.json").read_text(encoding="utf-8"))
    path = output / "01-反馈执行与独立审计.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    # 运行中快照只支持已保存输出的诊断，终态之后必须重新生成全分母复核。
    result = dict(time_beijing=now(), record_sha256=sha256(path), execution_status=record["status"], rows=[])
    for route in manifest["routes"]:
        for branch in ("full", "candidate"):
            parent_sha = route["initial_mesh_sha256"]
            for row in [r for r in record["rows"] if r["route"] == route["id"] and r["branch"] == branch]:
                if row["status"] != "published_under_sampled_and_vertex_protocol":
                    continue
                stem = route["id"] + "_" + row["event"]
                folder = output / (stem + "_" + branch + "_" + row["selected_method"])
                candidate_path = folder / "candidate.obj"
                mesh = trimesh.load(candidate_path, process=False)
                source = trimesh.load(output / (stem + "_" + branch + "_input") / "clean_source.obj", process=False)
                valid, metrics = mesh_valid_exact_contacts(mesh)
                geometry = global_geometry(mesh, source)
                # 新入口显式登记所用恢复参照；旧记录仍读取原始reference.obj。
                reference_row = next(r for r in record["rows"] if r["route"]==route["id"] and r["event"]==row["event"] and r["branch"]=="R")
                reference_path = output / (stem + "_reference") / reference_row.get("reference_used_file","reference.obj")
                # 累计参照按发布时相同加载协议复审，原始文件仍原样保留。
                reference = trimesh.load(reference_path, process=True, validate=True) if reference_path.exists() else None
                cumulative = global_geometry(mesh, reference) if reference is not None else None
                cumulative_valid = mesh_valid_exact_contacts(reference)[0] if reference is not None else False
                actual_sha = sha256(candidate_path)
                parent_ok = row["parent_sha256"] == parent_sha
                topology_ok = mesh.euler_number == source.euler_number
                fixed_ok = True
                if row["selected_method"] != "full":
                    attempt = next(a for a in row["attempts"] if a["status"] == "accepted_sampled")
                    before_path = folder / "before_projection.obj"
                    if not before_path.exists() and remote is not None:
                        command = shlex.split(attempt["execution"]["command"])
                        remote_output = command[command.index("--output") + 1]
                        retrieve(remote.client, remote.sftp, remote_output + "/before_projection.obj", before_path)
                    before = trimesh.load(before_path, process=False)
                    ids = np.asarray(attempt["vertex_original_ids"])
                    selected = ids >= 0
                    fixed_ok = np.array_equal(mesh.vertices[selected], source.vertices[ids[selected]])
                    fixed_ok = fixed_ok and np.array_equal(mesh.faces, before.faces)
                passed = valid and topology_ok and parent_ok and actual_sha == row["output_sha256"] and fixed_ok
                passed = passed and geometry["probe_max_mm"] <= .1 and cumulative_valid and cumulative["probe_max_mm"] <= .1
                result["rows"].append(dict(route=route["id"], event=row["event"], branch=branch,
                    passed=bool(passed), parent_hash_matches=parent_ok, output_hash_matches=actual_sha == row["output_sha256"],
                    fixed_original_vertices_exact=bool(fixed_ok), metrics=metrics,
                    source_geometry=geometry, cumulative_geometry=cumulative, reference_valid=cumulative_valid))
                parent_sha = actual_sha
    result.update(outputs=len(result["rows"]), passed=sum(x["passed"] for x in result["rows"]),
        scope="重新加载实际保存网格；距离仍为全部顶点与面积样本；报警集合复核不是完整自交证书")
    (output / "04-保存输出父链与几何复审.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(result["execution_status"], result["passed"], "/", result["outputs"])
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--port", type=int)
    args = parser.parse_args()
    remote = RemoteQuality(args.output, args.port) if args.port else None
    try:
        recheck(args.prepared, args.output, remote)
    finally:
        if remote:
            remote.sftp.close()
            remote.client.close()
