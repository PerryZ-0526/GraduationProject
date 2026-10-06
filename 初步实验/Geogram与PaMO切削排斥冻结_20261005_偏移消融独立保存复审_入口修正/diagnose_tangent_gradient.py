"""在既有隔离环境重放长路线失败输入，取得逐能量项梯度故障记录。"""
import argparse
import json
import shlex
from pathlib import Path
from run_constrained_batch import RemoteQuality,HERE
from run_geometry_study import execute,retrieve,PYTHON,save,now
from audit_followup_candidate import sha256


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port",type=int,required=True)
    parser.add_argument("--prior",type=Path,default=HERE/"实验结果/20261004_共同来源碎片修复公开长路线")
    parser.add_argument("--output",type=Path,default=HERE/"实验结果/20261004_切空间非有限梯度能量归因")
    parser.add_argument("--case",default="BP3D_FJ3384_重复长磨")
    parser.add_argument("--event",default="e3")
    args=parser.parse_args()
    prior=args.prior
    output=args.output
    output.mkdir(exist_ok=False)
    records=json.loads((prior/"01-反馈执行与独立审计.json").read_text(encoding="utf-8"))["rows"]
    row=next(r for r in records if r["route"]==args.case and r["event"]==args.event and r["branch"]=="candidate")
    attempt=row["attempts"][0]
    argv=shlex.split(attempt["execution"]["command"])
    index=argv.index("--source")
    old_worker=argv[index-1]
    arguments=argv[index:argv.index(">")]
    engine=RemoteQuality(output,args.port)
    try:
        if execute(engine.client,["mkdir",engine.remote])["returncode"]:
            raise RuntimeError("诊断目录创建失败")
        script=HERE/"diagnose_tangent_gradient_worker.py"
        engine.sftp.put(str(script),engine.remote+"/diagnostic.py")
        (output/script.name).write_bytes(script.read_bytes())
        arguments[arguments.index("--output")+1]=engine.remote+"/output"
        old_root=str(Path(old_worker).parent).replace("\\","/")
        diagnostic=engine.remote+"/gradient.json"
        run=execute(engine.client,["env","LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libstdc++.so.6","PYTHONPATH="+old_root,
            "GRADIENT_DIAGNOSTIC_OUTPUT="+diagnostic,"ORIGINAL_PLANAR_WORKER="+old_worker,PYTHON,engine.remote+"/diagnostic.py",*arguments],
            engine.remote+"/worker.log",timeout=900)
        retrieve(engine.client,engine.sftp,engine.remote+"/worker.log",output/"worker.log")
        retrieve(engine.client,engine.sftp,diagnostic,output/"gradient.json")
        report=dict(time_beijing=now(),run=run,original_attempt=attempt,diagnostic_code_sha256=sha256(script),
                    gradient=json.loads((output/"gradient.json").read_text(encoding="utf-8")),scope="故障复现，不发布网格，不改变作者能量")
        save(output/"01-逐能量项非有限梯度诊断.json",report)
        print(report["gradient"])
    finally:
        engine.close()


if __name__=="__main__":
    main()
