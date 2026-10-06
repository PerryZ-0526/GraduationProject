"""固定查询资产在用户GPU执行，独立有理数参照逐项比较分类与距离。"""
import argparse
import json
from pathlib import Path
import numpy as np
from run_constrained_batch import RemoteQuality,HERE
from run_geometry_study import execute,retrieve,save,now,PYTHON
from audit_followup_candidate import sha256
from pt_exact_reference import point_triangle_reference


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--inputs",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--port",type=int,required=True)
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    engine=RemoteQuality(args.output,args.port)
    try:
        if execute(engine.client,["mkdir",engine.remote])["returncode"]:
            raise RuntimeError("远端诊断目录不可创建")
        snapshots={}
        for path,name in [(HERE/"robust_pt_gpu.py","robust_pt_gpu.py"),(HERE/"run_pt_query_worker.py","run_pt_query_worker.py"),(args.inputs,"inputs.json")]:
            engine.sftp.put(str(path),engine.remote+"/"+name)
            (args.output/name).write_bytes(path.read_bytes())
            snapshots[name]=sha256(path)
            if execute(engine.client,["sha256sum",engine.remote+"/"+name])["stdout"].split()[0]!=snapshots[name]:
                raise ValueError("远端实际查询或代码摘要不匹配")
        environment=execute(engine.client,[PYTHON,"-c","import torch,warp,json;print(json.dumps({'gpu':torch.cuda.get_device_name(0),'torch':torch.__version__,'warp':warp.__version__}))"])
        run=execute(engine.client,["env","LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libstdc++.so.6","PYTHONPATH="+engine.remote,
            PYTHON,engine.remote+"/run_pt_query_worker.py","--inputs",engine.remote+"/inputs.json","--output",engine.remote+"/result.json"],engine.remote+"/worker.log",timeout=300)
        retrieve(engine.client,engine.sftp,engine.remote+"/worker.log",args.output/"worker.log")
        save(args.output/"01-GPU查询执行记录.json",{"time_beijing":now(),"run":run,"environment":environment,"snapshots":snapshots})
        if run["returncode"]:
            raise RuntimeError("查询执行失败，见worker.log")
        retrieve(engine.client,engine.sftp,engine.remote+"/result.json",args.output/"result.json")
        cases=json.loads(args.inputs.read_text(encoding="utf-8"))["cases"]
        result=json.loads((args.output/"result.json").read_text(encoding="utf-8"))
        rows=[]
        for i,case in enumerate(cases):
            kind,distance=point_triangle_reference(np.asarray(case["positions_normalized"],np.float32))
            improved=result["distances"][i][1]
            rows.append({"id":case["id"],"expected_kind":kind,"expected_distance":distance,
                "original_kind":result["types"][i][0],"improved_kind":result["types"][i][1],
                "original_distance":result["distances"][i][0],"improved_distance":improved,
                "classification_passed":result["types"][i][1]==kind,
                "distance_passed":bool(np.isfinite(improved) and abs(improved-distance)<=max(1e-12,abs(distance)*1e-5))})
        summary={"time_beijing":now(),"rows":rows,"classification_passed":sum(r["classification_passed"] for r in rows),
            "distance_passed":sum(r["distance_passed"] for r in rows),"total":len(rows),
            "scope":"同一FP32坐标的GPU分类距离与有理数最近点对拍；非导数、CCD或完整输出"}
        save(args.output/"02-GPU分类距离有理数对拍.json",summary)
        print(summary["classification_passed"],summary["distance_passed"],summary["total"],flush=True)
    finally:
        engine.close()
