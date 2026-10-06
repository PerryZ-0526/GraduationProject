"""独立重放指定公开路线的累计参照；不使用PaMO父网格构造参照。"""
import argparse
import json
import shlex
from pathlib import Path
import trimesh
from run_constrained_batch import RemoteQuality, HERE
from run_geometry_study import execute, retrieve, GEO, save, now
from audit_followup_candidate import sha256
from exact_alarm_contact import mesh_valid_exact_contacts
from run_constrained_feedback import global_geometry


def prefix_tools_through(route, event):
    """只重放截至目标事件的原工具，禁止借用后续切削几何。"""
    ids = [t["event_id"] for t in route["prefix_tools"]]
    if len(set(ids)) != len(ids) or event not in ids:
        raise ValueError("工具事件重复或目标事件不存在")
    return route["prefix_tools"][:ids.index(event)+1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--prepared", type=Path, default=HERE.parent / "可复用磨削测试集/公开浅磨批次_v2")
    parser.add_argument("--prior", type=Path, default=HERE / "实验结果/20261004_共同来源碎片修复公开骨面反馈")
    parser.add_argument("--output", type=Path, default=HERE / "实验结果/20261004_公开右肱骨累计参照恢复")
    parser.add_argument("--route", default="BP3D_FJ3368_交叉浅磨")
    parser.add_argument("--event", default="e3")
    args = parser.parse_args()
    prepared, prior, output = args.prepared, args.prior, args.output
    output.mkdir(exist_ok=False)
    rid, event = args.route, args.event
    manifest = json.loads((prepared / "01-完整范围冻结清单.json").read_text(encoding="utf-8"))
    route = next(r for r in manifest["routes"] if r["id"] == rid)
    tools = prefix_tools_through(route, event)
    records = json.loads((prior / "01-反馈执行与独立审计.json").read_text(encoding="utf-8"))["rows"]
    failed = next(r for r in records if r["route"] == rid and r["event"] == event and r["branch"] == "R")
    candidate_row = next(r for r in records if r["route"] == rid and r["event"] == event and r["branch"] == "candidate")
    command = shlex.split(failed["run"]["command"])
    index = command.index(GEO)
    initial_remote, union_remote = command[index+1:index+3]
    engine = RemoteQuality(output, args.port)
    report = dict(time_beijing=now(), rows=[], original_reference_failure=failed,
                  independence="初始骨面与原工具重放；不借用维护后网格生成参照", inputs=[],
                  route=rid,event=event,replayed_tool_events=[t["event_id"] for t in tools],
                  manifest_sha256=sha256(prepared / "01-完整范围冻结清单.json"))
    try:
        if execute(engine.client, ["mkdir", engine.remote])["returncode"]:
            raise RuntimeError("新恢复目录无法创建")
        for remote, name in ((initial_remote,"initial.obj"),(union_remote,"cumulative_union.obj")):
            retrieve(engine.client, engine.sftp, remote, output / name)
            report["inputs"].append(dict(file=name,sha256=sha256(output/name)))
            if name == "initial.obj" and sha256(output/name) != route["initial_mesh_sha256"]:
                raise ValueError("远端初态与冻结初态摘要不一致")
        # 两个固定对照：同累计工具禁共面简化，和从初态逐工具顺序差集。
        modes = [("cumulative_no_simplify", [GEO,initial_remote,union_remote,engine.remote+"/no_simplify.obj","--no-simplify"])]
        parent = initial_remote
        for tool in tools:
            destination = engine.remote + "/replay_" + tool["event_id"] + ".obj"
            tool_path = prepared / "inputs" / tool["mesh"]
            if sha256(tool_path) != tool["sha256"]:
                raise ValueError("冻结工具变化")
            remote_tool = engine.remote + "/" + tool["mesh"]
            engine.sftp.put(str(tool_path),remote_tool)
            run = execute(engine.client,[GEO,parent,remote_tool,destination],destination+".log",timeout=120)
            retrieve(engine.client,engine.sftp,destination+".log",output/ (tool["event_id"]+"_replay.log"))
            report.setdefault("sequential_runs",[]).append(run)
            if run["returncode"]:
                parent = None
                break
            parent = destination
        if parent:
            modes.append(("sequential_from_initial", None))
        for mode, argv in modes:
            remote = argv[3] if argv else parent
            run = execute(engine.client,argv,remote+".log",timeout=120) if argv else {"returncode":0}
            row = dict(mode=mode,run=run)
            report["rows"].append(row)
            if run["returncode"]:
                continue
            path = output / (mode+".obj")
            retrieve(engine.client,engine.sftp,remote,path)
            reference = trimesh.load(path,force="mesh",process=True,validate=True)
            valid, metrics = mesh_valid_exact_contacts(reference)
            row.update(sha256=sha256(path),valid=valid,metrics=metrics,candidate_checks=[])
            if valid:
                for attempt in candidate_row["attempts"]:
                    if attempt["status"] != "reference_unavailable":
                        continue
                    method = "boolean" if attempt["method"].startswith("planar") else "expanded"
                    candidate_path = prior / (rid+"_"+event+"_candidate_"+method) / "candidate.obj"
                    geometry = global_geometry(trimesh.load(candidate_path,process=False),reference)
                    row["candidate_checks"].append(dict(method=method,sha256=sha256(candidate_path),geometry=geometry,
                                                       passed=geometry["probe_max_mm"] <= .1))
        save(output / "01-独立累计参照恢复与保存候选核对.json", report)
        print([(r["mode"],r.get("valid"),r["run"]["returncode"]) for r in report["rows"]])
    finally:
        engine.close()


if __name__ == "__main__":
    main()
