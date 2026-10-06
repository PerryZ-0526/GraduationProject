"""取回同次独立参照失败的实际输入，隔离定位而不重试原布尔任务。"""
import argparse
import json
from pathlib import Path
import shlex
from run_constrained_batch import RemoteQuality
from run_geometry_study import retrieve,save,now,GEO
from audit_followup_candidate import sha256


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--port",type=int,required=True)
    args = parser.parse_args()
    report = json.loads((args.run/"01-反馈执行与独立审计.json").read_text(encoding="utf-8"))
    row = next(r for r in report["rows"] if r["route"] == "application_ct_original138" and r["event"] == "e11" and r["branch"] == "R")
    failure = row["recovery"]["runs"][-1]
    if failure["returncode"] == 0:
        raise ValueError("登记调用没有失败")
    parts = shlex.split(failure["command"])
    index = parts.index(GEO)
    paths = parts[index+1:index+4]
    args.output.mkdir(exist_ok=False)
    engine = RemoteQuality(args.run,args.port)
    try:
        if any(not path.startswith(engine.remote+"/") for path in paths):
            raise ValueError("失败输入不是本批隔离目录")
        files = []
        for path,name in ((paths[0],"raw_parent.obj"),(paths[1],"tool.obj"),(paths[2]+".log","geogram_failure.log")):
            retrieve(engine.client,engine.sftp,path,args.output/name)
            files.append(dict(file=name,remote_source=path,sha256=sha256(args.output/name)))
        save(args.output/"01-实际参照失败输入绑定.json",dict(time_beijing=now(),files=files,failed_call=failure,
            frame_event="e11",failed_replay_tool="e10",reference_row=row,
            scope="原初态工具重放到第十一个工具时的实际失败输入；不借维护输出、不重跑、不发布"))
        print("failure inputs retrieved",len(files))
    finally:
        engine.close()
