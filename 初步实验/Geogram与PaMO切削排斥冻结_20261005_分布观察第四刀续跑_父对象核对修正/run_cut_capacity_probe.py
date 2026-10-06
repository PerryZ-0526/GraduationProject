"""隔离进程增加接触容量，完整重跑真实第四刀GPU，不修改作者安装。"""

import argparse
import json
from pathlib import Path

from run_reference_cut_feedback import ReferenceCutEngine
from run_geometry_study import execute, retrieve, save, now, PYTHON
from audit_followup_candidate import sha256


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--previous", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    args.output.mkdir(exist_ok=False)
    ReferenceCutEngine.prepared = args.prepared
    engine = ReferenceCutEngine(args.output, args.port)
    report = {"生成时间": now(), "修改时间及修改内容": "首次生成，第四刀容量重跑先冻结",
              "文档概述": "单次完整作者GPU，容量由2的25次方增至26次方；不删除接触或改变距离精度",
              "索引目录": ["environment", "inputs", "execution"], "status": "running",
              "new_max_blocks": 1 << 26, "original_max_blocks": 1 << 25}
    record = args.output / "01-第四刀接触容量GPU复跑.json"
    try:
        # 只执行基础上传与环境核查；本入口不启动候选CPU修正。
        from run_cut_exclusion_continuation import CertifiedCutEngine
        report["environment"] = CertifiedCutEngine.setup(engine)
        inputs = args.previous / "BP3D_FJ3384_交叉浅磨_e3_candidate_input"
        old = json.loads((args.previous / "01-输入保护续跑与发布记录.json").read_text("utf8"))["rows"][1]
        tool = args.prepared / "inputs" / next(t["mesh"] for t in engine.routes["BP3D_FJ3384_交叉浅磨"]["prefix_tools"] if t["event_id"] == "e3")
        paths = [(inputs / "clean_source.obj", "source.obj"), (inputs / "clean_labels.json", "labels.json"), (tool, "tool.obj")]
        report["inputs"] = {}
        for path, name in paths:
            if sha256(path) != old["attempt"]["inputs_sha256"][name]:
                raise ValueError("第四刀同输入摘要已改变")
            engine.sftp.put(str(path), engine.remote + "/" + name)
            actual = execute(engine.client, ["sha256sum", engine.remote + "/" + name])["stdout"].split()[0]
            if actual != sha256(path):
                raise ValueError("远端实际输入摘要不符")
            report["inputs"][name] = actual
        # 类构造器仅在独立GPU进程内增加缓冲容量，作者配置文件和数学核函数保持原样。
        code = "\n".join([
            "import hashlib,inspect,json",
            "from pamo_safe_project import Stage3Config",
            "config_path=inspect.getfile(Stage3Config)",
            "digest=hashlib.sha256(open(config_path,'rb').read()).hexdigest()",
            "assert digest=='df1eb24db57394c32e31f6d67a58cd7ef6c25febc11aff39c5e9503ee82d6390'",
            "original=Stage3Config.__init__",
            "def larger(self,*args,**kwargs):",
            "    original(self,*args,**kwargs)",
            "    assert self.max_blocks == 1<<25",
            "    self.max_blocks=1<<26",
            "    print(json.dumps({'original_config_sha256':digest,'max_blocks':self.max_blocks}),flush=True)",
            "Stage3Config.__init__=larger",
            "import run_constrained_worker as worker",
            "worker.main()"])
        launcher = args.output / "capacity_launcher.py"
        launcher.write_text(code, encoding="utf8")
        engine.sftp.put(str(launcher), engine.remote + "/capacity_launcher.py")
        report["launcher_sha256"] = sha256(launcher)
        save(record, report)
        command = ["env", "LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libstdc++.so.6", "PYTHONPATH=" + engine.remote,
            PYTHON, engine.remote + "/capacity_launcher.py", "--source", engine.remote + "/source.obj",
            "--labels", engine.remote + "/labels.json", "--tool", engine.remote + "/tool.obj",
            "--executable", engine.remote + "/constrained_remesh", "--method", "full", "--output", engine.remote + "/output"]
        run = execute(engine.client, command, engine.remote + "/worker.log", timeout=900)
        retrieve(engine.client, engine.sftp, engine.remote + "/worker.log", args.output / "worker.log")
        report["execution"] = run
        log = (args.output / "worker.log").read_text("utf8")
        report["capacity_overflow"] = "exceeds max_blocks" in log or "Number of contacts" in log
        if not run["returncode"]:
            for name in ("candidate.obj", "details.json"):
                retrieve(engine.client, engine.sftp, engine.remote + "/output/" + name, args.output / name)
            report["raw_output_sha256"] = sha256(args.output / "candidate.obj")
        report.update(status="completed", finished_beijing=now(),
                      GPU_execution_passed_without_capacity_retry=bool(not run["returncode"] and not report["capacity_overflow"]))
        save(record, report)
        print("GPU_capacity_probe", report["GPU_execution_passed_without_capacity_retry"], flush=True)
    finally:
        engine.close()


if __name__ == "__main__":
    main()
