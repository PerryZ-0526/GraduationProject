"""冻结解析CCD输入的GPU执行入口，动态库路径与完整投影保持一致。"""
import argparse
import json
from pathlib import Path
from run_constrained_batch import RemoteQuality,HERE
from run_geometry_study import execute,retrieve,save,now,PYTHON
from audit_followup_candidate import sha256


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--inputs",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--port",type=int,required=True)
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    digest=json.loads((args.inputs.parent/"03-点三角形输入摘要.json").read_text(encoding="utf-8"))
    if sha256(args.inputs)!=digest["ccd_inputs_sha256"]:
        raise ValueError("解析CCD冻结输入摘要不匹配")
    engine=RemoteQuality(args.output,args.port)
    try:
        if execute(engine.client,["mkdir",engine.remote])["returncode"]:
            raise RuntimeError("远端CCD目录不可创建")
        names=("robust_pt_gpu.py","precision_collision_install.py","run_precision_ccd_worker.py")
        for name in names:
            engine.sftp.put(str(HERE/name),engine.remote+"/"+name)
            (args.output/name).write_bytes((HERE/name).read_bytes())
        engine.sftp.put(str(args.inputs),engine.remote+"/inputs.json")
        (args.output/"inputs.json").write_bytes(args.inputs.read_bytes())
        run=execute(engine.client,["env","LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libstdc++.so.6","PYTHONPATH="+engine.remote,
            PYTHON,engine.remote+"/run_precision_ccd_worker.py","--inputs",engine.remote+"/inputs.json","--output",engine.remote+"/result.json"],engine.remote+"/worker.log",timeout=300)
        retrieve(engine.client,engine.sftp,engine.remote+"/worker.log",args.output/"worker.log")
        save(args.output/"01-CCD解析GPU执行记录.json",{"time_beijing":now(),"run":run,
            "source_sha256":{name:sha256(HERE/name) for name in names},"input_sha256":sha256(args.inputs)})
        if run["returncode"]:
            raise RuntimeError("CCD执行失败，见worker.log")
        retrieve(engine.client,engine.sftp,engine.remote+"/result.json",args.output/"02-CCD解析控制结果.json")
        result=json.loads((args.output/"02-CCD解析控制结果.json").read_text(encoding="utf-8"))
        print(result["passed"],result["rows"],flush=True)
    finally:
        engine.close()
