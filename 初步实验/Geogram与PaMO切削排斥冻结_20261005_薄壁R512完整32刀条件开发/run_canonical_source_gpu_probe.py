"""四次预声明完整GPU对照：原始两种排列与同一规范输入两次重复。"""

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
    for name in ("prepared", "previous", "assets", "build-record", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    args.output.mkdir(exist_ok=False)
    rid = "BP3D_FJ3384_交叉浅磨"
    old = json.loads((args.previous / "01-统一配置完整父反馈记录.json").read_text("utf8"))
    launcher = args.previous / "capacity_launcher.py"
    worker = Path(__file__).with_name("run_constrained_worker.py")
    observer = Path(__file__).with_name("order_observation_launcher.py")
    if sha256(launcher) != old["capacity_entry"]["actual_remote_sha256"] or sha256(worker) != old["capacity_entry"]["original_worker_sha256"]:
        raise ValueError("冻结容量入口或作者工作入口不符")
    inputs = [("原始排列0", "原始_0_clean_source.obj", "原始_0_clean_labels.json"),
              ("原始排列1", "原始_1_clean_source.obj", "原始_1_clean_labels.json"),
              ("规范重复0", "规范_0_source.obj", "规范_0_labels.json"),
              ("规范重复1", "规范_1_source.obj", "规范_1_labels.json")]
    report = {"生成时间": now(), "修改时间及修改内容": "首次生成，四次完整GPU输入预冻结",
              "文档概述": "仅更换同几何输入排列，均使用隔离排序邻接扩展；额外读回不用于性能结论",
              "索引目录": ["protocol", "environment", "rows"], "status": "running", "rows": [],
              "protocol": [{"name": name, "source_sha256": sha256(args.assets / source),
                            "labels_sha256": sha256(args.assets / labels)} for name, source, labels in inputs],
              "new_GPU_calls_budget": 4, "observer_sha256": sha256(observer), "worker_sha256": sha256(worker),
              "capacity_launcher_sha256": sha256(launcher), "driver_sha256": sha256(Path(__file__)),
              "asset_manifest_sha256": sha256(args.assets / "01-同几何布尔源排列冻结对照.json")}
    record = args.output / "01-同几何排列完整GPU冻结对照.json"
    ReferenceCutEngine.prepared = args.prepared
    engine = ReferenceCutEngine(args.output, args.port)
    try:
        report["environment"] = CertifiedCutEngine.setup(engine)
        for path, remote_name in ((worker, "original_run_constrained_worker.py"), (launcher, "original_capacity_launcher.py"), (observer, "run_constrained_worker.py")):
            engine.sftp.put(str(path), engine.remote + "/" + remote_name)
            if execute(engine.client, ["sha256sum", engine.remote + "/" + remote_name])["stdout"].split()[0] != sha256(path):
                raise ValueError("远端实际入口摘要不同")
        build = json.loads(args.build_record.read_text("utf8"))
        if build["status"] != "completed":
            raise ValueError("隔离扩展构建未完成")
        extension = next(item for item in build["builds"] if item["variant"] == "sorted")
        report["extension"] = extension
        config = args.output / "order_extension.json"
        config.write_text(json.dumps(extension, ensure_ascii=False), "utf8")
        engine.sftp.put(str(config), engine.remote + "/order_extension.json")
        tool = args.prepared / "inputs" / next(t["mesh"] for t in engine.routes[rid]["prefix_tools"] if t["event_id"] == "e0")
        if sha256(tool) != old["rows"][0]["attempt"]["inputs_sha256"]["tool.obj"]:
            raise ValueError("首刀工具与原实际输入不同")
        report["tool_sha256"] = sha256(tool)
        save(record, report)
        for index, (name, source_name, label_name) in enumerate(inputs):
            source, labels = args.assets / source_name, args.assets / label_name
            if sha256(source) != report["protocol"][index]["source_sha256"] or sha256(labels) != report["protocol"][index]["labels_sha256"]:
                raise ValueError("预声明输入已改变")
            folder = args.output / name
            row = RemoteQuality.run(engine, source, labels, tool, "full", folder)
            row["name"] = name
            # 先保留真实执行记录，阶段取回异常也不能抹去已发生的GPU调用。
            report["rows"].append(row)
            save(record, report)
            if row["execution"]["returncode"]:
                continue
            stages = folder / "阶段观测"
            stages.mkdir()
            remote = engine.remote + "/" + name + "/stage_observations"
            engine.sftp.get(remote + "/observation.json", str(stages / "阶段摘要.json"))
            row["observation"] = json.loads((stages / "阶段摘要.json").read_text("utf8"))
            row["stages"] = {}
            for stage in ("stage1", "stage2", "stage3"):
                path = stages / (stage + ".obj")
                engine.sftp.get(remote + "/" + stage + ".obj", str(path))
                item = {"sha256": sha256(path)}
                if index:
                    before_index = 2 if index == 3 else 0
                    before = args.output / inputs[before_index][0] / "阶段观测" / (stage + ".obj")
                    if before.exists():
                        item["comparison_run"] = inputs[before_index][0]
                        item["same_bytes"] = sha256(before) == sha256(path)
                        item["geometry_difference"] = global_geometry(trimesh.load(path, force="mesh", process=False), trimesh.load(before, force="mesh", process=False))
                row["stages"][stage] = item
            save(record, report)
            print(name, "GPU完整结束", flush=True)
        report.update(status="completed", finished_beijing=now())
        save(record, report)
    finally:
        engine.close()


if __name__ == "__main__":
    main()
