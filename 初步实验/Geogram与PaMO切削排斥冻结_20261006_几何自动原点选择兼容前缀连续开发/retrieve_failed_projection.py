"""取回同批失败投影前对象和实际编译副本，不重跑GPU或改写发布记录。"""
import argparse
import json
from pathlib import Path
import shlex
import shutil
from audit_followup_candidate import sha256
from run_constrained_batch import RemoteQuality
from run_geometry_study import retrieve, save, now


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--route", required=True)
    parser.add_argument("--event", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    report = json.loads((args.run/"01-反馈执行与独立审计.json").read_text(encoding="utf-8"))
    row = next(r for r in report["rows"] if r["route"] == args.route and r["event"] == args.event and r["branch"] == "candidate")
    args.output.mkdir(exist_ok=False)
    engine = RemoteQuality(args.run, args.port)
    files = []
    try:
        source = args.run/(args.route+"_"+args.event+"_candidate_input")/"clean_source.obj"
        shutil.copyfile(source, args.output/"source.obj")
        files.append(dict(file="source.obj", sha256=sha256(args.output/"source.obj"), source=str(source)))
        for attempt in row["attempts"]:
            command = shlex.split(attempt["execution"]["command"])
            remote = command[command.index("--output")+1]
            if not remote.startswith(engine.remote+"/") or attempt["execution"]["returncode"] == 0:
                raise ValueError("不是同批失败投影任务")
            method = "expanded" if attempt["method"].startswith("expanded") else "boolean"
            folder = args.output/method
            folder.mkdir()
            retrieve(engine.client, engine.sftp, remote+"/before_projection.obj", folder/"before_projection.obj")
            original = args.run/(args.route+"_"+args.event+"_candidate_"+method)
            for name in ("worker.log", "diff_trace.json"):
                shutil.copyfile(original/name, folder/name)
            for path in folder.iterdir():
                files.append(dict(file=str(path.relative_to(args.output)), sha256=sha256(path)))
        # 这些模块位于同批隔离根目录，作者安装位置不读取或修改。
        folder = args.output/"compiled_evidence"
        folder.mkdir()
        for name in ("preserved_geometry_system.py", "preserved_install.json",
                     "preserved_geometry_snapshots/preserved_collision_energy.py",
                     "preserved_geometry_snapshots/preserved_ccd.py"):
            target = folder/Path(name).name
            retrieve(engine.client, engine.sftp, engine.remote+"/"+name, target)
            files.append(dict(file=str(target.relative_to(args.output)), sha256=sha256(target)))
        save(args.output/"01-实际投影失败对象绑定.json", dict(time_beijing=now(), files=files, row=row,
            scope="同批实际失败对象、完整异常接触及编译副本；不执行新GPU任务、不发布"))
        print("retrieved files", len(files))
    finally:
        engine.close()
