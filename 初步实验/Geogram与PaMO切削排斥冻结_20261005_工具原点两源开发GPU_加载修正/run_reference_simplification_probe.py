"""同一初态和工具前缀对照Geogram默认与禁共面简化，旧负结果保留。"""
import argparse
import json
from pathlib import Path
import trimesh
from run_constrained_batch import RemoteQuality
from run_geometry_study import execute, retrieve, save, now, GEO
from independent_reference_recovery import validate_replayed_reference
from verify_precision_resume import digest, read


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--route", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    manifest_path = args.prepared / "01-完整范围冻结清单.json"
    route = next(route for route in read(manifest_path)["routes"] if route["id"] == args.route)
    args.output.mkdir(parents=True, exist_ok=False)
    engine = RemoteQuality(args.output, args.port)
    report = {"time_beijing": now(), "status": "running", "rows": [], "route": route["id"],
              "manifest_sha256": digest(manifest_path), "script_sha256": digest(Path(__file__)),
              "scope": "独立原初态顺序差集参照诊断，不使用维护父链，不修改既有验收"}
    try:
        if execute(engine.client, ["mkdir", engine.remote])["returncode"]:
            raise RuntimeError("参照诊断目录已存在或不可创建")
        report["geogram_binary_sha256"] = execute(engine.client, ["sha256sum", GEO])["stdout"].split()[0]
        for mode in ("default", "no_simplify"):
            parent = engine.remote+"/"+mode+"_initial.obj"
            initial = args.prepared / "inputs" / route["initial_mesh"]
            if digest(initial) != route["initial_mesh_sha256"]:
                raise ValueError("初态摘要变化")
            engine.sftp.put(str(initial), parent)
            for tool in route["prefix_tools"]:
                source = args.prepared / "inputs" / tool["mesh"]
                if digest(source) != tool["sha256"]:
                    raise ValueError("工具摘要变化")
                remote_tool = engine.remote+"/"+tool["mesh"]
                engine.sftp.put(str(source), remote_tool)
                name = mode+"_"+tool["event_id"]
                destination = engine.remote+"/"+name+".obj"
                command = [GEO, parent, remote_tool, destination]
                if mode == "no_simplify":
                    command.append("--no-simplify")
                run = execute(engine.client, command, destination+".log", timeout=120)
                retrieve(engine.client, engine.sftp, destination+".log", args.output/(name+".log"))
                row = {"mode": mode, "event": tool["event_id"], "tool_sha256": tool["sha256"], "run": run}
                if run["returncode"] == 0:
                    target = args.output/(name+".obj")
                    retrieve(engine.client, engine.sftp, destination, target)
                    raw = trimesh.load(target, process=False)
                    _, validation = validate_replayed_reference(raw)
                    row.update(validation=validation, raw_sha256=digest(target))
                    parent = destination
                report["rows"].append(row)
                save(args.output/"01-参照简化选项对照.json", report)
                print(mode, tool["event_id"], run["returncode"], row.get("validation", {}).get("accepted"), flush=True)
                if run["returncode"]:
                    break
        report.update(status="completed_with_recorded_results", finished_beijing=now())
        save(args.output/"01-参照简化选项对照.json", report)
    finally:
        engine.close()


if __name__ == "__main__":
    main()
