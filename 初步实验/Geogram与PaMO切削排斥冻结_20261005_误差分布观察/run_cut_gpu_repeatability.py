"""固定已经执行的首刀全部输入与容量，两次完整GPU检查实际重复性。"""

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
    record = args.output / "01-同输入完整GPU重复性核对.json"
    try:
        report["environment"] = CertifiedCutEngine.setup(engine)
        launcher = args.previous / "capacity_launcher.py"
        worker = Path(__file__).with_name("run_constrained_worker.py")
        if sha256(launcher) != old["capacity_entry"]["actual_remote_sha256"] or sha256(worker) != old["capacity_entry"]["original_worker_sha256"]:
            raise ValueError("同容量入口或GPU工作源码不符")
        engine.sftp.put(str(worker), engine.remote + "/original_run_constrained_worker.py")
        engine.sftp.put(str(launcher), engine.remote + "/run_constrained_worker.py")
        if execute(engine.client, ["sha256sum", engine.remote + "/run_constrained_worker.py"])["stdout"].split()[0] != sha256(launcher):
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
            report["rows"].append(row)
            save(record, report)
            print("repeat", index + 1, "raw_match", row.get("raw_sha_matches_previous"), flush=True)
        report.update(status="completed", finished_beijing=now())
        save(record, report)
    finally:
        engine.close()


if __name__ == "__main__":
    main()
