"""冻结两档方法的新参数输入，仅从初态及原工具独立重放累计参照。"""

import argparse
import getpass
import json
from pathlib import Path

from audit_followup_candidate import sha256
from run_constrained_batch import RemoteQuality
from run_cut_exclusion_recovery import exact_recovery
from run_geometry_study import execute, now, save
from audit_cut_embedding import CHECKER


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    mp = args.prepared / "01-完整范围冻结清单.json"
    manifest = json.loads(mp.read_text("utf-8-sig"))
    # 只读独立输入与冻结代码；本入口不初始化PaMO，也不调用GPU。
    args.output.mkdir(exist_ok=False)
    config = dict(line.split("=", 1) for line in (Path(__file__).parents[2] / ".env").read_text("utf8").splitlines()
                  if line and not line.startswith("#"))
    prompt = getpass.getpass
    try:
        getpass.getpass = lambda _: config["CUDA_SSH_PASSWORD"]
        engine = RemoteQuality(args.output, args.port)
    finally:
        getpass.getpass = prompt
        del config
    record = args.output / "01-新参数独立参照全范围执行.json"
    report = {"生成时间": now(), "修改时间及修改内容": "首次生成，独立重放全部冻结事件",
              "文档概述": "每路线三参照完成后分别冻结绑定；拒绝保留原分母，不参与候选调参",
              "索引目录": ["environment", "rows", "summary"], "status": "running", "rows": [],
              "manifest_sha256": sha256(mp), "new_GPU_calls": 0}
    save(record, report)
    try:
        if execute(engine.client, ["mkdir", engine.remote])["returncode"]:
            raise RuntimeError("独立参照远端目录不能创建")
        report["environment"] = {"remote": engine.remote,
            "exact_checker_sha256": execute(engine.client, ["sha256sum", CHECKER])["stdout"].split()[0]}
        for route in manifest["routes"]:
            route_root = args.output / route["id"]
            route_root.mkdir()
            binding = {"生成时间": now(), "修改时间及修改内容": "本路线所有参照终态后一次冻结",
                       "文档概述": "仅初态与截至当前事件的冻结工具；不使用任何维护父网格",
                       "索引目录": ["rows"], "manifest_sha256": sha256(mp), "rows": []}
            for event in route["cutting_prefix_ids"]:
                folder = route_root / f"{route['id']}_{event}_reference"
                folder.mkdir()
                mesh, details = exact_recovery(engine, args.prepared, route, event, "unused", folder, False)
                row = {"route": route["id"], "event": event,
                       "reference_sha256": sha256(folder / "validated_reference.obj") if mesh is not None else None,
                       "status": "reference_valid" if mesh is not None else "reference_rejected", "details": details}
                binding["rows"].append(row)
                report["rows"].append(row)
                save(folder / "01-本事件独立参照执行.json", details)
                save(record, report)
                print(route["id"], event, row["status"], flush=True)
            save(route_root / "01-独立累计参照绑定.json", binding)
        report.update(status="completed", finished_beijing=now(), summary={
            "planned": sum(len(r["cutting_prefix_ids"]) for r in manifest["routes"]),
            "accepted": sum(r["status"] == "reference_valid" for r in report["rows"]),
            "rejected": sum(r["status"] == "reference_rejected" for r in report["rows"])})
        save(record, report)
    finally:
        engine.close()


if __name__ == "__main__":
    main()
