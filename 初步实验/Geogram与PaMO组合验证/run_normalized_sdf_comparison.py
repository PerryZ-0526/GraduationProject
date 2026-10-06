"""冻结两张已捕获工作源的SDF对照，仅使用隔离远端目录。"""

import argparse
import getpass
import hashlib
import json
import os
from pathlib import Path
import sys


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--captured", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.core.resolve()))
    from run_constrained_batch import RemoteQuality
    from run_geometry_study import execute, retrieve, save, now, PYTHON
    frozen = json.loads(Path(__file__).with_name("01-执行前源码冻结.json").read_text("utf8"))
    for item in frozen["files"]:
        if sha(Path(__file__).with_name(item["file"])) != item["sha256"]:
            raise ValueError("冻结执行源码改变")
    capture_record = args.captured / "01-两源实际工作网格与精确嵌入核查.json"
    captured = json.loads(capture_record.read_text("utf8"))
    if captured["status"] != "completed":
        raise ValueError("实际工作源捕获尚未结束")
    args.output.mkdir(exist_ok=False)
    report = {"生成时间": now(), "修改时间及修改内容": "首次生成，两例四次SDF核调用预算",
              "文档概述": "既有负例开发对照，不改旧42事件或执行完整PaMO",
              "索引目录": ["rows"], "status": "running", "rows": [],
              "capture_record_sha256": sha(capture_record), "freeze_sha256": sha(Path(__file__).with_name("01-执行前源码冻结.json")),
              "full_PaMO_calls": 0}
    record = args.output / "01-两源GPU符号场对照总记录.json"
    save(record, report)
    # 凭据只在本机读取并用于建立连接，不写进远端命令或实验报告。
    cfg = dict(line.split("=", 1) for line in (args.core.parents[1] / ".env").read_text("utf8").splitlines() if line and not line.startswith("#"))
    previous = getpass.getpass
    os.environ["GPU_SSH_HOST"] = "connect.westb.seetacloud.com"
    try:
        getpass.getpass = lambda _: cfg["CUDA_SSH_PASSWORD"]
        engine = RemoteQuality(args.output, 51667)
    finally:
        getpass.getpass = previous
        del cfg
    try:
        if execute(engine.client, ["mkdir", engine.remote])["returncode"]:
            raise ValueError("远端隔离目录不可创建")
        for name in ("compare_normalized_sdf_worker.py", "normalized_sdf_chain.py"):
            path = Path(__file__).with_name(name)
            engine.sftp.put(str(path), engine.remote + "/" + name)
            if execute(engine.client, ["sha256sum", engine.remote + "/" + name])["stdout"].split()[0] != sha(path):
                raise ValueError("实际远端源码摘要不同")
        for event in ("e1", "e0"):
            source = args.captured / event / "03-CPU归一化SDF源.obj"
            metadata = args.captured / event / "04-实际GPU工作源捕获记录.json"
            bound = next(r for r in captured["rows"] if r["event"] == event)
            if sha(source) != next(r["stored_sha256"] for r in bound["checks"] if r["file"] == source.name):
                raise ValueError("归一化源与实际捕获总记录不同")
            for path, name in [(source, event + ".obj"), (metadata, event + ".json")]:
                engine.sftp.put(str(path), engine.remote + "/" + name)
                if execute(engine.client, ["sha256sum", engine.remote + "/" + name])["stdout"].split()[0] != sha(path):
                    raise ValueError("实际GPU输入摘要不同")
            remote_output = engine.remote + "/" + event
            run = execute(engine.client, ["env", "LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libstdc++.so.6",
                "PYTHONPATH=" + engine.remote, PYTHON, engine.remote + "/compare_normalized_sdf_worker.py",
                "--source", engine.remote + "/" + event + ".obj", "--metadata", engine.remote + "/" + event + ".json",
                "--output", remote_output], engine.remote + "/" + event + ".log", timeout=300)
            local = args.output / event
            local.mkdir()
            retrieve(engine.client, engine.sftp, engine.remote + "/" + event + ".log", local / "GPU运行.log")
            row = {"event": event, "execution": run, "source_sha256": sha(source), "metadata_sha256": sha(metadata)}
            report["rows"].append(row)
            if run["returncode"] == 0:
                for name in ("01-整理后归一化源.obj", "02-两份实际GPU符号场.npz", "03-符号场对照记录.json"):
                    retrieve(engine.client, engine.sftp, remote_output + "/" + name, local / name)
                row["result"] = json.loads((local / "03-符号场对照记录.json").read_text("utf8"))
                if row["result"]["fields_npz_sha256"] != sha(local / "02-两份实际GPU符号场.npz"):
                    raise ValueError("保存符号场摘要不同")
            save(record, report)
            print(event, run["returncode"], row.get("result", {}).get("comparison"), flush=True)
        report.update(status="completed_with_recorded_outcomes", finished_beijing=now())
        save(record, report)
    finally:
        engine.sftp.close()
        engine.client.close()


if __name__ == "__main__":
    main()
