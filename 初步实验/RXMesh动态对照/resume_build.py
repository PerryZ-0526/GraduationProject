"""调用既有remote.py，逐阶段恢复隔离构建并保存脱敏连接失败记录。"""
import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
import subprocess
import sys


HERE = Path(__file__).resolve().parent
REMOTE = "/root/autodl-tmp/graduation_project/build_rxmesh_dynamic_20260908_141858"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("setup", "dependencies", "configure", "build"))
    args = parser.parse_args()
    now = datetime.now(timezone(timedelta(hours=8)))
    output = HERE / "实验结果" / (now.strftime("%Y%m%d_%H%M%S") + "_" + args.phase)
    output.mkdir(parents=True, exist_ok=False)
    record = {"time_beijing": now.strftime("%Y-%m-%d %H:%M:%S"), "phase": args.phase, "steps": []}
    calls = [
        ["--put", str(HERE / "run_build.sh"), REMOTE + "/run_build.sh"],
        ["--command", "cd " + REMOTE + "; bash run_build.sh " + args.phase
         + " > " + output.name + ".log 2>&1; rc=$?; cat " + output.name + ".log; exit $rc"],
    ]
    for index, call in enumerate(calls):
        result = subprocess.run(
            [sys.executable, "-B", "-X", "utf8", str(HERE.parents[1] / "初步实验/CUDA远程验证/remote.py"), *call],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding="utf-8", timeout=620, check=False,
        )
        # 日志保留错误类别，删除连接端点；不读取.env或持久化配置。
        content = re.sub(r"Unable to connect to port [^\r\n]+", "Unable to connect to configured SSH endpoint", result.stdout)
        (output / (str(index) + ".log")).write_text(content, encoding="utf-8")
        record["steps"].append({"arguments": call, "exit_code": result.returncode})
        print(content[-4000:], flush=True)
        if result.returncode:
            record["status"] = "connection_failed" if "NoValidConnectionsError" in content else "step_failed"
            break
    else:
        record["status"] = "phase_completed"
    (output / "record.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    print("记录目录：", output, flush=True)
    return 0 if record["status"] == "phase_completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
