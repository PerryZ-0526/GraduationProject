"""同输入完整GPU阶段观测，两次执行先冻结，保留额外读回声明。"""

import argparse
import json
from pathlib import Path

import trimesh

from run_reference_cut_feedback import ReferenceCutEngine
from run_cut_exclusion_continuation import CertifiedCutEngine
from run_constrained_batch import RemoteQuality
from audit_followup_candidate import sha256
from run_constrained_feedback import global_geometry
from run_geometry_study import execute, save, now


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--previous", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    old = json.loads((args.previous / "01-统一配置完整父反馈记录.json").read_text("utf8"))
    first = old["rows"][0]
    rid = old["selected_route"]
    if old["status"] == "running" or first["event"] != "e0" or first["attempt"]["execution"]["returncode"]:
        raise ValueError("本入口要求已完成首刀GPU记录")
    args.output.mkdir(exist_ok=False)
    ReferenceCutEngine.prepared = args.prepared
    engine = ReferenceCutEngine(args.output, args.port)
    report = {"生成时间": now(), "修改时间及修改内容": "首次生成，两次同输入完整GPU先冻结",
              "文档概述": "检查首刀原GPU数值与几何重复性，不运行新修正或连续路线",
              "索引目录": ["environment", "rows"], "status": "running", "rows": [], "new_GPU_calls_budget": 2,
              "previous_record_sha256": sha256(args.previous / "01-统一配置完整父反馈记录.json")}
    record = args.output / "01-同输入GPU简化逐调用定位.json"
    try:
        report["environment"] = CertifiedCutEngine.setup(engine)
        launcher = args.previous / "capacity_launcher.py"
        worker = Path(__file__).with_name("run_constrained_worker.py")
        if sha256(launcher) != old["capacity_entry"]["actual_remote_sha256"] or sha256(worker) != old["capacity_entry"]["original_worker_sha256"]:
            raise ValueError("同容量入口或GPU工作源码不符")
        engine.sftp.put(str(worker), engine.remote + "/original_run_constrained_worker.py")
        engine.sftp.put(str(launcher), engine.remote + "/original_capacity_launcher.py")
        observer = Path(__file__).with_name("iteration_observation_launcher.py")
        engine.sftp.put(str(observer), engine.remote + "/run_constrained_worker.py")
        report["observer_sha256"] = sha256(observer)
        if execute(engine.client, ["sha256sum", engine.remote + "/run_constrained_worker.py"])["stdout"].split()[0] != sha256(observer):
            raise ValueError("实际重复运行入口摘要不符")
        source = args.previous / f"{rid}_e0_candidate_input/clean_source.obj"
        labels = source.with_name("clean_labels.json")
        tool = args.prepared / "inputs" / next(t["mesh"] for t in engine.routes[rid]["prefix_tools"] if t["event_id"] == "e0")
        if {name: sha256(path) for name, path in (("source.obj", source), ("labels.json", labels), ("tool.obj", tool))} != first["attempt"]["inputs_sha256"]:
            raise ValueError("全部实际首刀GPU输入摘要不符")
        previous_raw = args.previous / f"{rid}_e0_candidate_boolean/raw_full_candidate.obj"
        if sha256(previous_raw) != first["attempt"]["raw_full_output_sha256"]:
            raise ValueError("原GPU对象已改变")
        original = trimesh.load(previous_raw, force="mesh", process=False)
        save(record, report)
        for index in range(2):
            folder = args.output / f"同输入GPU第{index + 1}次"
            row = RemoteQuality.run(engine, source, labels, tool, "full", folder)
            log = (folder / "worker.log").read_text("utf8")
            row["capacity_overflow"] = "exceeds max_blocks" in log or "Number of contacts" in log
            row["capacity_declared_67108864"] = '"max_blocks": 67108864' in log
            if not row["execution"]["returncode"]:
                path = folder / "candidate.obj"
                row["raw_sha_matches_previous"] = sha256(path) == sha256(previous_raw)
                row["geometry_difference_to_previous"] = global_geometry(trimesh.load(path, force="mesh", process=False), original)
            # 成功阶段均取回真实对象，并用相同几何探针比较两次执行。
            stages = folder / "阶段观测"
            stages.mkdir()
            remote_stage = engine.remote + "/" + folder.name + "/stage_observations"
            row["stage_observations"] = {}
            for stage in ("stage1", "stage2", "stage3"):
                path = stages / (stage + ".obj")
                engine.sftp.get(remote_stage + "/" + stage + ".obj", str(path))
                item = {"sha256": sha256(path)}
                if index:
                    before = args.output / "同输入GPU第1次" / "阶段观测" / (stage + ".obj")
                    item["same_bytes"] = sha256(before) == sha256(path)
                    item["geometry_difference"] = global_geometry(trimesh.load(path, force="mesh", process=False), trimesh.load(before, force="mesh", process=False))
                row["stage_observations"][stage] = item
            engine.sftp.get(remote_stage + "/observation.json", str(stages / "阶段摘要.json"))
            observation = json.loads((stages / "阶段摘要.json").read_text("utf8"))
            row["observed_tensors"] = observation["tensors"]
            row["simplification_calls"] = observation["simplification_calls"]
            if index:
                previous_calls = report["rows"][0]["simplification_calls"]
                differences = []
                for before_call, after_call in zip(previous_calls, row["simplification_calls"]):
                    if before_call["output"] != after_call["output"]:
                        differences.append(after_call["index"])
                row["first_output_divergence"] = differences[0] if differences else None
                if differences:
                    first_index = differences[0]
                    row["first_divergence_input_equal"] = previous_calls[first_index]["input"] == row["simplification_calls"][first_index]["input"]
                    for run_index, destination in ((1, args.output / "同输入GPU第1次" / "阶段观测"), (2, stages)):
                        name = f"iteration_{first_index:03d}.obj"
                        remote_folder = engine.remote + f"/同输入GPU第{run_index}次/stage_observations/iterations/"
                        engine.sftp.get(remote_folder + name, str(destination / name))
                    before_mesh = args.output / "同输入GPU第1次" / "阶段观测" / f"iteration_{first_index:03d}.obj"
                    after_mesh = stages / f"iteration_{first_index:03d}.obj"
                    row["first_divergence_geometry"] = global_geometry(trimesh.load(after_mesh, force="mesh", process=False), trimesh.load(before_mesh, force="mesh", process=False))
            report["rows"].append(row)
            save(record, report)
            print("repeat", index + 1, "raw_match", row.get("raw_sha_matches_previous"), flush=True)
        report.update(status="completed", finished_beijing=now())
        save(record, report)
    finally:
        engine.close()


if __name__ == "__main__":
    main()
